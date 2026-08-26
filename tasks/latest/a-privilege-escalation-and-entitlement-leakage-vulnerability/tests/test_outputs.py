"""Verification for entitlement lineage corruption reconciler (Go privilege coordinator replayer)."""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
import shutil
import struct
import subprocess
import zlib
from pathlib import Path
from typing import Any

import pytest

REPORT_PATH = Path("/app/build/delegation_integrity_snapshot.json")
REPORT_FIRST = Path("/logs/verifier/report_first.json")
VERIFIER_DIR = Path("/logs/verifier")
DATA_DIR = Path("/app/delegation_federation_slices")
CATALOG_PATH = DATA_DIR / "federation_slice_roll.json"
APP_DIR = Path("/app")
BINARY = APP_DIR / "build" / "delegationintegrity"
MAIN_GO = APP_DIR / "cmd" / "delegationintegrity" / "main.go"
MAKEFILE = APP_DIR / "Makefile"

SLICE_KEY_ORDER = [
    "delegation_slice_id",
    "status",
    "duplicate_events_skipped",
    "inheritance_journal",
    "inheritance_edges",
    "coordinators",
    "findings",
]

INHERITANCE_JOURNAL_KEY_ORDER = [
    "format_version",
    "records_total",
    "records_valid",
    "records_rejected",
    "dup_seq_rejects",
    "truncated_tail",
    "payload_bytes",
]

FINDING_KINDS = frozenset(
    {
        "UNATTESTED_ACCESS",
        "DOMAIN_BLEED",
        "RESURRECTED_ENTITLEMENT",
        "ENTITLEMENT_ESCALATION",
        "UNTRUSTED_INHERITANCE",
        "UNKNOWN_TARGET",
        "UNKNOWN_COORDINATOR",
        "DUPLICATE_COORDINATOR",
        "DUPLICATE_INHERITANCE",
        "LATERAL_GHOSTING",
        "RESTRICTED_TIER",
        "INHERITANCE_ASYMMETRY",
        "OPEN_GHOST_PATH",
        "SOVEREIGN_UNBOUND",
    }
)

FINDING_ID_RE = re.compile(r"^[^:]+::[^:]+::\d{4}$")
DELEGATION_POISON_RISK_VALUES = frozenset({"contained", "elevated", "critical"})
ACCESS_EVAL_STOP_KINDS = frozenset(
    {
        "UNKNOWN_TARGET",
        "UNKNOWN_COORDINATOR",
        "UNTRUSTED_INHERITANCE",
        "DOMAIN_BLEED",
        "RESTRICTED_TIER",
        "UNATTESTED_ACCESS",
    }
)
POST_REPLAY_AUDIT_KINDS = frozenset(
    {"INHERITANCE_ASYMMETRY", "OPEN_GHOST_PATH", "SOVEREIGN_UNBOUND"}
)

DYNAMIC_SWAP_SLICE = "delegation_slice_11"
MATRIX_SWAP_SLICE = "delegation_slice_05"

SLICE_FINDING_REQUIREMENTS: dict[str, frozenset[str]] = {
    "delegation_slice_01": frozenset(),
    "delegation_slice_02": frozenset({"DUPLICATE_COORDINATOR"}),
    "delegation_slice_03": frozenset({"DOMAIN_BLEED"}),
    "delegation_slice_04": frozenset({"ENTITLEMENT_ESCALATION", "RESURRECTED_ENTITLEMENT"}),
    "delegation_slice_05": frozenset({"INHERITANCE_ASYMMETRY", "UNATTESTED_ACCESS"}),
    "delegation_slice_06": frozenset({"UNKNOWN_TARGET"}),
    "delegation_slice_07": frozenset({"UNKNOWN_COORDINATOR"}),
    "delegation_slice_08": frozenset({"DUPLICATE_INHERITANCE"}),
    "delegation_slice_09": frozenset({"ENTITLEMENT_ESCALATION", "LATERAL_GHOSTING"}),
    "delegation_slice_10": frozenset({"OPEN_GHOST_PATH", "RESTRICTED_TIER", "SOVEREIGN_UNBOUND"}),
    "delegation_slice_11": frozenset({"INHERITANCE_ASYMMETRY"}),
    "delegation_slice_12": frozenset({"OPEN_GHOST_PATH"}),
    "delegation_slice_13": frozenset({"SOVEREIGN_UNBOUND"}),
    "delegation_slice_14": frozenset(),
    "delegation_slice_15": frozenset(),
    "delegation_slice_16": frozenset({"UNTRUSTED_INHERITANCE"}),
    "delegation_slice_17": frozenset({"INHERITANCE_ASYMMETRY"}),
    "delegation_slice_18": frozenset({"UNKNOWN_COORDINATOR"}),
    "delegation_slice_19": frozenset(),
    "delegation_slice_20": frozenset({"ENTITLEMENT_ESCALATION"}),
    "delegation_slice_21": frozenset(),
    "delegation_slice_22": frozenset(),
    "delegation_slice_23": frozenset({"OPEN_GHOST_PATH", "SOVEREIGN_UNBOUND"}),
    "delegation_slice_24": frozenset(),
    "delegation_slice_25": frozenset({"INHERITANCE_ASYMMETRY"}),
    "delegation_slice_26": frozenset({"OPEN_GHOST_PATH", "RESTRICTED_TIER"}),
    "delegation_slice_27": frozenset(),
    "delegation_slice_28": frozenset({"ENTITLEMENT_ESCALATION"}),
}

SLICE_SPOT_CHECKS: dict[str, Any] = {
    "delegation_slice_05": lambda row: row["inheritance_journal"]["dup_seq_rejects"] == 1,
    "delegation_slice_14": lambda row: row["duplicate_events_skipped"] == 1,
    "delegation_slice_20": lambda row: row["inheritance_journal"]["truncated_tail"] == 1,
    "delegation_slice_21": lambda row: (
        row["status"] == "VALID"
        and row["duplicate_events_skipped"] == 1
        and row["inheritance_journal"]["payload_bytes"] >= 4500
    ),
    "delegation_slice_22": lambda row: row["status"] == "VALID" and row["findings"] == [],
    "delegation_slice_24": lambda row: row["status"] == "VALID" and row["findings"] == [],
    "delegation_slice_03": lambda row: any(
        f["kind"] == "DOMAIN_BLEED" and f["detail"] == "orders" for f in row["findings"]
    ),
    "delegation_slice_09": lambda row: {"ENTITLEMENT_ESCALATION", "LATERAL_GHOSTING"} <= {
        f["kind"] for f in row["findings"]
    },
    "delegation_slice_12": lambda row: any(
        f["kind"] == "OPEN_GHOST_PATH" and f["event_seq"] == 5 for f in row["findings"]
    ),
    "delegation_slice_23": lambda row: [f["kind"] for f in row["findings"]]
    == ["OPEN_GHOST_PATH", "SOVEREIGN_UNBOUND"],
    "delegation_slice_25": lambda row: row["duplicate_events_skipped"] == 1
    and any(f["kind"] == "INHERITANCE_ASYMMETRY" and f["event_seq"] == 100 for f in row["findings"]),
    "delegation_slice_26": lambda row: {"RESTRICTED_TIER", "OPEN_GHOST_PATH"}
    <= {f["kind"] for f in row["findings"]}
    and any(f["kind"] == "RESTRICTED_TIER" and f["entity_id"] == "vend" for f in row["findings"]),
    "delegation_slice_27": lambda row: row["status"] == "VALID"
    and row["duplicate_events_skipped"] == 1
    and {c["coordinator_id"] for c in row["coordinators"]} == {"a", "b"},
    "delegation_slice_28": lambda row: any(
        f["kind"] == "ENTITLEMENT_ESCALATION" and f["detail"] == "z:need" for f in row["findings"]
    ),
}
ORIGINAL_PROTECTED_SHA256: dict[str, str] = {
    "Makefile": "4e05de3df24d81f709093d30752619278a8423a409b928d35e36e42ecb305e28",
    "go.mod": "9d38d44f30d8b329c2c1bce138f4a636cc38726d6e0c32bd362f608856907af9",
    "go.sum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "provenance_charters/DELEGATION_INTEGRITY_SNAPSHOT_SCHEMA.md": "57c3edad4ccf7241a4c83060c3f256cab5169c29a1c58eced5446323ced1c735",
    "provenance_charters/DELEGATION_LINEAGE_CORRUPTION_RULES.md": "af51aa4d31c0af241284a9f48f0d1faf051e5fe0223498452846824da23a996e",
    "provenance_charters/ELWJ1_INHERITANCE_JOURNAL_CODEC.md": "40b4e01990e87ff827e22d690d69b776677363dbbfa34cb89418a277699a2371",
    "delegation_federation_slices/.DS_Store": "2f2a1a44868e19c5d95ba4e96c56a4cb2ce136ac899325dffce402c858e96430",
    "delegation_federation_slices/delegation_slice_01/inheritance_journal.elwj": "48bc14a07c3398213d1640bc1acd680fa0ca5faf79735e9eb8fa5d838bec3885",
    "delegation_federation_slices/delegation_slice_01.json": "45d59bad10af5de32c75fe50158c956d90f446f96b16d8750c0e568138f3d5a9",
    "delegation_federation_slices/delegation_slice_02/inheritance_journal.elwj": "debe4b91eb99e6a54d4ec3019767f08fc6f7c1ec1a1b45fff76bb27815593139",
    "delegation_federation_slices/delegation_slice_02.json": "19a7ae6ffeb6ee66efe132cb7060b832c26ee1513c7992efb2188d33ed9f6b2d",
    "delegation_federation_slices/delegation_slice_03/inheritance_journal.elwj": "f24864a2a5baffacd17de5006e3a011b721137390217b691720423973a1c70f0",
    "delegation_federation_slices/delegation_slice_03.json": "50c63c2e1bb03c4ff5a8e753558c6d7adf3b633cb552ae9b0021b9d0b2a1f263",
    "delegation_federation_slices/delegation_slice_04/inheritance_journal.elwj": "41edfb78279311f8bdc8e424edbc7be8c43aa0d9fa1a21313567c2a8f5f2dfcf",
    "delegation_federation_slices/delegation_slice_04.json": "c3eb3999cb6f372bbd13f0da17ea507333ec209ff2d7e99bf55df63f212581fe",
    "delegation_federation_slices/delegation_slice_05/inheritance_journal.elwj": "a00f0dff526e3163f4bd0bf3fb99bcfe659f85e287a494be34b8f55c3edbbda1",
    "delegation_federation_slices/delegation_slice_05.json": "1cd399781f8b6aaf3e5a718b2586a44edf944ef530b569f44ae50d6ab2828ce9",
    "delegation_federation_slices/delegation_slice_06/inheritance_journal.elwj": "95f12ca46ce29f7f90f4c528f89ac4dac65ae95392b55e4a9f2f27ec61492d1b",
    "delegation_federation_slices/delegation_slice_06.json": "80e32f5f66847aa93d179199e579a728b583696ac1df5fb3fe26a2280ea767f0",
    "delegation_federation_slices/delegation_slice_07/inheritance_journal.elwj": "809c043c30e83aed04fa17ceda86d7468d4a2a5de767df444c46cbf1fe1756da",
    "delegation_federation_slices/delegation_slice_07.json": "cb68371c88d4b39f21d1cfbe789f02942ec15c94219cbe7f8b22f06fca984040",
    "delegation_federation_slices/delegation_slice_08/inheritance_journal.elwj": "da802470c75af5021e807ff7cb6317e395b6bae1632f2d4d6ab62a4ef5da42fa",
    "delegation_federation_slices/delegation_slice_08.json": "3b6574b88d4d7ba41a90531c2c27dffbd02f4dc0d7ddc11e01334ae23017e66e",
    "delegation_federation_slices/delegation_slice_09/inheritance_journal.elwj": "20b92e9b764a7819704fe78cbac26fd677074921489ebb319766b0847f766316",
    "delegation_federation_slices/delegation_slice_09.json": "eb4a89a7ab34c3c7e398ac93016b24493a9a50956a5561a23efee8cc9fdea35a",
    "delegation_federation_slices/delegation_slice_10/inheritance_journal.elwj": "a2d915cd13c28cacd233eda1aa32c6433fc552b9acc44e188a3949a88f287d68",
    "delegation_federation_slices/delegation_slice_10.json": "cde877e3f3b3c5708798645f9f9117fc78d1d9c598f2f6cf2dc1944f07ffaba2",
    "delegation_federation_slices/delegation_slice_11/inheritance_journal.elwj": "75ddda06f7d25e7c7f76a8dee16ca89246f15d7508a7307e4ae97d1302a85972",
    "delegation_federation_slices/delegation_slice_11.json": "00c43c9e1c2ad6fad78840cb510b24d60bade805fa50dd4ca145d30f3ed0427a",
    "delegation_federation_slices/delegation_slice_12/inheritance_journal.elwj": "f22f7e79deada0c46680b1b9a27bcc0cdeb1e60d671d2653af825aff294682f3",
    "delegation_federation_slices/delegation_slice_12.json": "f961544e48c578b7b5f7dbe6fabe101118313d3183bfde4e5af24a3649fa05c6",
    "delegation_federation_slices/delegation_slice_13/inheritance_journal.elwj": "c0aac09af75adef69e8efc69cf97fbb2a7362b8e58a9512478c40556e55ce275",
    "delegation_federation_slices/delegation_slice_13.json": "a3bfb8cd0d1f05d317a7ee1fa89e487539d1a524fa16e4a95200319a75449301",
    "delegation_federation_slices/delegation_slice_14/inheritance_journal.elwj": "2004ef69e1853a5729c3824be9b1636f809ae6c113e6f06f47a14a5aed954daa",
    "delegation_federation_slices/delegation_slice_14.json": "ec2db99d77633a50f6e407066eeb3a221f978c4bde34376ee0fa2323a5609942",
    "delegation_federation_slices/delegation_slice_15/inheritance_journal.elwj": "b55ad0b71301c736337963ebbf75805fafd794856fa7938320009e41dcfe7269",
    "delegation_federation_slices/delegation_slice_15.json": "2150a04c0dfbf03bbb3a9aedb0c5c17b492b429b451fb073015939f7a47b85b1",
    "delegation_federation_slices/delegation_slice_16/inheritance_journal.elwj": "8a4ef02837c7eb2c5a19c316d56f26877b898d12afb5b21bbb031f213cb8ca30",
    "delegation_federation_slices/delegation_slice_16.json": "edaab7b642bbf8672e3d2bf72efaf689bbeb1d965ba06d9d2f84e36ab6d4060d",
    "delegation_federation_slices/delegation_slice_17/inheritance_journal.elwj": "81373348648f2289267138a0670af5362e5b6d0af549d8fc7bd01367bef3f392",
    "delegation_federation_slices/delegation_slice_17.json": "66d47598f67190d8454dff84d7c5b2a68129accf74467b17df86b4e923acbde6",
    "delegation_federation_slices/delegation_slice_18/inheritance_journal.elwj": "99bf0caa87306815130a52dc8e5eeb97aa4301a6f6021a702bed19d3fe0bd9c2",
    "delegation_federation_slices/delegation_slice_18.json": "c0e77d900cac96cdcef840072bf64acf4e82fafa86cee30ca468e3accaa681bb",
    "delegation_federation_slices/delegation_slice_19/inheritance_journal.elwj": "71f04ece706c4fa4fb22f5cfaefc89154e75c701cce9c1e9c2fb4dc493b24f45",
    "delegation_federation_slices/delegation_slice_19.json": "0b9eebd9ec93c482376e99d945de45d9382a8ec882392dbfa02ea33517aff088",
    "delegation_federation_slices/delegation_slice_20/inheritance_journal.elwj": "7158d019ec7b0c7add746a8c06ee339c4e48dd8101a9861dcd274c684fb379cf",
    "delegation_federation_slices/delegation_slice_20.json": "4ff5aa007756f2f3d2bcb2ae63e1e935e72c833332091965ac5c99f85b327667",
    "delegation_federation_slices/delegation_slice_21/inheritance_journal.elwj": "24141ffb0448a7f36f577fdb1fbd6dfa4d5676af7b80e75e6e91de247b7fd22b",
    "delegation_federation_slices/delegation_slice_21.json": "0feb630b0e6ea0deee5e5222761dce8046e9f51e4ecca8c55ff085ecb75e4906",
    "delegation_federation_slices/delegation_slice_22/inheritance_journal.elwj": "e42014d9fe271ea2ace6e8b1ddfa4b92a55398f1f355d0dd63e768ad151e40d4",
    "delegation_federation_slices/delegation_slice_22.json": "c92b399de81c25eeedd797299fe542a3f1af689c932fb5d0b6837892b6ac63e0",
    "delegation_federation_slices/delegation_slice_23/inheritance_journal.elwj": "b8619350d582e26ac81bdf8f30f18cbfc50ca1d646191de4fdcf3f504cdff6c3",
    "delegation_federation_slices/delegation_slice_23.json": "d080ddbab91b54284628d92d73e4f31e630718b949f1a33a17a975d1ffdf8397",
    "delegation_federation_slices/delegation_slice_24/inheritance_journal.elwj": "e3f626a4a33fa778ba4dcf50ead5d3cb6fddd598cba461f8e615b9cb1466658f",
    "delegation_federation_slices/delegation_slice_24.json": "f3a7cd3954a989f59a596c0b0a3dfb3c41944e23b3b8bdc9c8ddaa28c6975145",
    "delegation_federation_slices/delegation_slice_25/inheritance_journal.elwj": "e4dd2f21b633a37541491c9c1bb9d6d357b318fa095f9933ec4de3a279e53471",
    "delegation_federation_slices/delegation_slice_25.json": "35df728f2d4cf6836e30338b9e67f80c2fca336b74a925437c6678c80f1cb021",
    "delegation_federation_slices/delegation_slice_26/inheritance_journal.elwj": "3b49c21f6e62bc28507a9734910e939eb60e44119cd5957f4fe6be5e7c6f8522",
    "delegation_federation_slices/delegation_slice_26.json": "876e2310c26fbc9de296b5d8a0e1580f62ef36191b01b8d64f0aa01d9ea8e8ab",
    "delegation_federation_slices/delegation_slice_27/inheritance_journal.elwj": "e7beb9109435d7a2b974250642b8605d650739177a2c3e2ecf7b1ee9c41f1e4c",
    "delegation_federation_slices/delegation_slice_27.json": "20c6457b28134dc8ec015d6457a35c13b4630d956c2f7e833fad1ff7e2bcdbc0",
    "delegation_federation_slices/delegation_slice_28/inheritance_journal.elwj": "d958521c768b70722e3080f7fa2f9f54f75ea880f032633d676ee1004e094210",
    "delegation_federation_slices/delegation_slice_28.json": "5d62c2855fe724dcdcc426dd59174a387da9f1a69c77a9e7c79b675bbab79ef2",
    "delegation_federation_slices/federation_slice_roll.json": "7ff8e2630fdd35553efe584e281715bc2679eaf3ace4da54ba67bfbebe4a438c",
}



def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode_inheritance_journal_bytes(data: bytes) -> tuple[dict[str, int], list[dict[str, Any]]]:
    """Decode ELWJ little-endian inheritance_journal per ELWJ1_INHERITANCE_JOURNAL_CODEC.md."""
    if len(data) < 8 or data[:4] != b"ELWJ":
        raise ValueError("bad magic")
    format_version = struct.unpack_from("<I", data, 4)[0]
    stats: dict[str, int] = {
        "format_version": format_version,
        "records_total": 0,
        "records_valid": 0,
        "records_rejected": 0,
        "dup_seq_rejects": 0,
        "truncated_tail": 0,
        "payload_bytes": 0,
    }
    if format_version != 1:
        raise ValueError("unsupported format_version")
    off = 8
    seen: set[int] = set()
    events: list[dict[str, Any]] = []
    while off < len(data):
        if off + 12 > len(data):
            stats["records_rejected"] += 1
            stats["truncated_tail"] = 1
            break
        record_seq, flags, reserved, plen = struct.unpack_from("<I H H I", data, off)
        off += 12
        stats["records_total"] += 1
        reason = ""
        if reserved != 0:
            reason = "BAD_RESERVED"
        elif flags != 0:
            reason = "BAD_FLAGS"
        elif plen > 5120:
            reason = "LEN_OVERFLOW"
        elif record_seq in seen:
            reason = "DUP_SEQ"
        if reason == "LEN_OVERFLOW":
            if off + plen + 4 <= len(data):
                off += plen + 4
                stats["records_rejected"] += 1
                seen.add(record_seq)
                continue
            stats["records_rejected"] += 1
            stats["truncated_tail"] = 1
            break
        if off + plen + 4 > len(data):
            stats["records_rejected"] += 1
            stats["truncated_tail"] = 1
            break
        payload = data[off : off + plen]
        off += plen
        checksum = struct.unpack_from("<I", data, off)[0]
        off += 4
        if reason == "":
            hdr = struct.pack("<I H H I", record_seq, flags, reserved, plen)
            if zlib.crc32(hdr + payload) & 0xFFFFFFFF != checksum:
                reason = "BAD_CRC"
        seen.add(record_seq)
        if reason:
            stats["records_rejected"] += 1
            if reason == "DUP_SEQ":
                stats["dup_seq_rejects"] += 1
            continue
        try:
            events.append(json.loads(payload.decode("utf-8")))
        except json.JSONDecodeError:
            stats["records_rejected"] += 1
            continue
        stats["records_valid"] += 1
        stats["payload_bytes"] += plen
    return stats, events


def decode_inheritance_journal(path: Path) -> tuple[dict[str, int], list[dict[str, Any]]]:
    return decode_inheritance_journal_bytes(path.read_bytes())

def _protected_paths_on_disk() -> set[str]:
    out: set[str] = set()
    for rel in ("Makefile", "go.mod", "go.sum"):
        out.add(rel)
    for subdir in ("provenance_charters", "delegation_federation_slices"):
        for path in (APP_DIR / subdir).rglob("*"):
            if path.is_file():
                out.add(path.relative_to(APP_DIR).as_posix())
    return out


def _event_payload(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, separators=(",", ":")).encode("utf-8")


def _pack_elwj_record(
    record_seq: int,
    flags: int,
    reserved: int,
    payload: bytes,
    *,
    checksum: int | None = None,
) -> bytes:
    hdr = struct.pack("<I H H I", record_seq, flags, reserved, len(payload))
    if checksum is None:
        checksum = zlib.crc32(hdr + payload) & 0xFFFFFFFF
    return hdr + payload + struct.pack("<I", checksum)


def _build_elwj(records: list[tuple[int, int, int, bytes]]) -> bytes:
    out = b"ELWJ" + struct.pack("<I", 1)
    for record_seq, flags, reserved, payload in records:
        out += _pack_elwj_record(record_seq, flags, reserved, payload)
    return out


def _register_event(
    seq: int,
    event_id: str,
    coordinator_id: str,
    *,
    tier: str = "operational",
    business_unit: str = "identity-core",
) -> dict[str, Any]:
    return {
        "seq": seq,
        "event_id": event_id,
        "coordinator_id": coordinator_id,
        "kind": "REGISTER_COORDINATOR",
        "privilege_tier": tier,
        "business_unit": business_unit,
    }


def _compound_adversarial_elwj_blob(seed: int) -> bytes:
    """Deterministic multi-frame ELWJ captures; not present in bundled fixtures."""
    if seed == 0:
        ev = _register_event(1, "m0", "matrix-a")
        return _build_elwj([(1, 0, 0, _event_payload(ev))])
    if seed == 1:
        ev = _register_event(1, "m1a", "matrix-b")
        payload = _event_payload(ev)
        return _build_elwj([(1, 0, 0, payload), (1, 0, 0, _event_payload({**ev, "event_id": "m1b"}) )])
    if seed == 2:
        good = _register_event(2, "m2", "matrix-c")
        payload = _event_payload(good)
        bad_header = struct.pack("<I H H I", 1, 0, 0, len(payload))
        return (
            b"ELWJ"
            + struct.pack("<I", 1)
            + bad_header
            + payload
            + struct.pack("<I", 0)
            + _pack_elwj_record(2, 0, 0, payload)
        )
    if seed == 3:
        oversize = b"\x00" * 5200
        header = struct.pack("<I H H I", 1, 0, 0, len(oversize))
        checksum = struct.pack("<I", zlib.crc32(header + oversize) & 0xFFFFFFFF)
        return b"ELWJ" + struct.pack("<I", 1) + header + oversize + checksum
    if seed == 4:
        oversize = b"\x00" * 5200
        header = struct.pack("<I H H I", 1, 0, 0, len(oversize))
        return b"ELWJ" + struct.pack("<I", 1) + header + oversize[:100]
    if seed == 5:
        return b"ELWJ" + struct.pack("<I", 1) + struct.pack("<I H H I", 1, 0, 0, 64)[:8]
    if seed == 6:
        return _build_elwj(
            [
                (3, 0, 0, _event_payload(_register_event(3, "m6c", "matrix-d"))),
                (1, 0, 0, _event_payload(_register_event(1, "m6a", "matrix-e"))),
                (2, 0, 0, _event_payload(_register_event(2, "m6b", "matrix-f"))),
            ]
        )
    if seed == 7:
        ev1 = _register_event(1, "m7a", "matrix-g")
        ev5 = _register_event(5, "m7e", "matrix-h")
        p1 = _event_payload(ev1)
        p5 = _event_payload(ev5)
        oversize = b"\x00" * 5200
        oh = struct.pack("<I H H I", 4, 0, 0, len(oversize))
        oc = struct.pack("<I", zlib.crc32(oh + oversize) & 0xFFFFFFFF)
        bad2 = struct.pack("<I H H I", 2, 0, 0, len(p1))
        return (
            b"ELWJ"
            + struct.pack("<I", 1)
            + _pack_elwj_record(1, 0, 0, p1)
            + bad2
            + p1
            + struct.pack("<I", 0)
            + _pack_elwj_record(1, 0, 0, p1)
            + oh
            + oversize
            + oc
            + _pack_elwj_record(5, 0, 0, p5)
        )
    if seed == 8:
        ev = _register_event(1, "m8a", "matrix-i")
        base = _build_elwj([(1, 0, 0, _event_payload(ev))])
        ev2 = _register_event(2, "m8b", "matrix-i")
        payload = _event_payload(ev2)
        header = struct.pack("<I H H I", 2, 0, 0, len(payload))
        return base + header[:8]
    if seed == 9:
        ev = _register_event(1, "m9a", "matrix-j")
        payload = _event_payload(ev)
        return _build_elwj([(1, 0, 0, payload)]) + _pack_elwj_record(1, 0, 0, payload)
    if seed == 10:
        return _build_elwj(
            [
                (1, 0, 0, _event_payload(_register_event(1, "m10a", "relay-ten"))),
                (2, 0, 1, _event_payload(_register_event(2, "m10b", "relay-ten"))),
            ]
        )
    if seed == 11:
        ev1 = _register_event(1, "m11a", "matrix-k")
        ev3 = _register_event(3, "m11c", "matrix-k")
        p1 = _event_payload(ev1)
        bad_header = struct.pack("<I H H I", 2, 0, 0, len(p1))
        return (
            b"ELWJ"
            + struct.pack("<I", 1)
            + _pack_elwj_record(1, 0, 0, p1)
            + bad_header
            + p1
            + struct.pack("<I", 0xBADC0DE)
            + _pack_elwj_record(3, 0, 0, _event_payload(ev3))
        )

    if seed == 12:
        ev = _register_event(1, "m12", "matrix-l")
        payload = _event_payload(ev)
        return _build_elwj([(1, 0, 0x01, payload)])
    if seed == 13:
        ev = _register_event(1, "m13", "matrix-m")
        payload = _event_payload(ev)
        return _build_elwj([(1, 0, 0x02, payload)])
    if seed == 14:
        good = _register_event(1, "m14g", "matrix-n")
        gp = _event_payload(good)
        return _build_elwj([(1, 0, 0, gp), (1, 0, 0, _event_payload({**good, "event_id": "m14d"}))])
    if seed == 15:
        ev = _register_event(1, "m15", "matrix-o")
        payload = _event_payload(ev)
        hdr = struct.pack("<I H H I", 1, 0, 0, len(payload))
        return b"ELWJ" + struct.pack("<I", 1) + hdr + payload + struct.pack("<I", 0xDEADBEEF)
    if seed == 16:
        bad = b"{not-json"
        return _build_elwj([(1, 0, 0, bad)])
    if seed == 17:
        ev = _register_event(1, "m17", "matrix-p")
        payload = _event_payload(ev)
        return b"ELWJ" + struct.pack("<I", 1) + struct.pack("<I H H I", 1, 0, 0, len(payload)) + payload[:4]
    if seed == 18:
        ev1 = _register_event(1, "m18a", "matrix-q")
        ev2 = _register_event(2, "m18b", "matrix-q")
        p1, p2 = _event_payload(ev1), _event_payload(ev2)
        oversize = b"\x00" * 5200
        oh = struct.pack("<I H H I", 3, 0, 0, len(oversize))
        oc = struct.pack("<I", zlib.crc32(oh + oversize) & 0xFFFFFFFF)
        return (
            b"ELWJ" + struct.pack("<I", 1)
            + _pack_elwj_record(1, 0, 0, p1)
            + _pack_elwj_record(1, 0, 0, _event_payload({**ev1, "event_id": "m18d"}))
            + oh + oversize + oc
            + _pack_elwj_record(2, 0, 0, p2)
        )
    if seed == 19:
        pad = "x" * 4500
        ev = {
            "seq": 1, "event_id": "m19", "coordinator_id": "matrix-r",
            "kind": "REGISTER_COORDINATOR", "privilege_tier": "operational",
            "business_unit": "identity-core", "_pad": pad,
        }
        return _build_elwj([(1, 0, 0, _event_payload(ev))])
    if seed == 20:
        ev_a = _register_event(5, "m20a", "alpha", business_unit="tenant-a")
        grant = {
            "seq": 5, "event_id": "m20g", "coordinator_id": "zeta",
            "grantor_coordinator": "alpha", "grantee_coordinator": "beta",
            "kind": "GRANT_INHERITANCE",
        }
        ev_b = _register_event(5, "m20b", "beta", business_unit="tenant-a")
        return _build_elwj([
            (1, 0, 0, _event_payload(grant)),
            (2, 0, 0, _event_payload(ev_a)),
            (3, 0, 0, _event_payload(ev_b)),
        ])
    if seed == 21:
        ev_v = _register_event(1, "m21v", "vendor-x", tier="vendor")
        ev_s = _register_event(2, "m21s", "sov-y", tier="sovereign")
        grant = {
            "seq": 3, "event_id": "m21g", "coordinator_id": "sov-y",
            "grantor_coordinator": "vendor-x", "grantee_coordinator": "sov-y",
            "kind": "GRANT_INHERITANCE",
        }
        return _build_elwj([
            (1, 0, 0, _event_payload(ev_v)),
            (2, 0, 0, _event_payload(ev_s)),
            (3, 0, 0, _event_payload(grant)),
        ])
    if seed == 22:
        ev_a = _register_event(1, "m22a", "alpha")
        ev_b = _register_event(2, "m22b", "beta")
        revoke = {
            "seq": 3, "event_id": "m22r", "coordinator_id": "alpha",
            "grantor_coordinator": "alpha", "grantee_coordinator": "beta",
            "kind": "REVOKE_INHERITANCE",
        }
        return _build_elwj([
            (1, 0, 0, _event_payload(ev_a)),
            (2, 0, 0, _event_payload(ev_b)),
            (3, 0, 0, _event_payload(revoke)),
        ])
    if seed == 23:
        ev1 = _register_event(1, "m23a", "alpha", tier="vendor")
        ev2 = _register_event(2, "m23b", "beta")
        grant = {
            "seq": 3, "event_id": "m23g", "coordinator_id": "alpha",
            "grantor_coordinator": "alpha", "grantee_coordinator": "beta",
            "kind": "GRANT_INHERITANCE",
        }
        bind = {"seq": 4, "event_id": "m23e4", "coordinator_id": "beta", "kind": "BIND_ENTITLEMENT", "entitlement_key": "governance:audit"}
        dup = {"seq": 99, "event_id": "m23e4", "coordinator_id": "beta", "kind": "BIND_ENTITLEMENT", "entitlement_key": "governance:admin"}
        return _build_elwj([
            (1, 0, 0, _event_payload(ev1)),
            (2, 0, 0, _event_payload(ev2)),
            (3, 0, 0, _event_payload(grant)),
            (4, 0, 0, _event_payload(bind)),
            (5, 0, 0, _event_payload(dup)),
        ])


    if seed == 24:
        # Underscore fold: Tenant_A == tenant-a after canonicalization → no DOMAIN_BLEED.
        ev_a = {
            "seq": 1, "event_id": "u1", "coordinator_id": "alpha",
            "kind": "REGISTER_COORDINATOR", "privilege_tier": "operational",
            "business_unit": " Tenant_A ",
        }
        ev_b = {
            "seq": 2, "event_id": "u2", "coordinator_id": "beta",
            "kind": "REGISTER_COORDINATOR", "privilege_tier": "operational",
            "business_unit": "tenant-a",
        }
        grant = {
            "seq": 3, "event_id": "u3", "coordinator_id": "alpha",
            "grantor_coordinator": "alpha", "grantee_coordinator": "beta",
            "kind": "GRANT_INHERITANCE",
        }
        access = {
            "seq": 4, "event_id": "u4", "coordinator_id": "beta",
            "requestor_id": "alpha", "eval_target_id": "beta",
            "kind": "ACCESS_EVAL", "action": "GET",
            "has_governance_attestation": True, "propagated_entitlements": [],
        }
        return _build_elwj([
            (1, 0, 0, _event_payload(ev_a)),
            (2, 0, 0, _event_payload(ev_b)),
            (3, 0, 0, _event_payload(grant)),
            (4, 0, 0, _event_payload(access)),
        ])
    if seed == 25:
        # Whitespace-only event_ids never dedup; trimmed duplicate later does.
        ev_a = _register_event(1, "   ", "alpha")
        ev_b = _register_event(2, "\t", "beta")
        grant = {
            "seq": 3, "event_id": " keep ", "coordinator_id": "alpha",
            "grantor_coordinator": "alpha", "grantee_coordinator": "beta",
            "kind": "GRANT_INHERITANCE",
        }
        dup = {
            "seq": 4, "event_id": "keep", "coordinator_id": "alpha",
            "grantor_coordinator": "alpha", "grantee_coordinator": "beta",
            "kind": "GRANT_INHERITANCE",
        }
        return _build_elwj([
            (1, 0, 0, _event_payload(ev_a)),
            (2, 0, 0, _event_payload(ev_b)),
            (3, 0, 0, _event_payload(grant)),
            (4, 0, 0, _event_payload(dup)),
        ])
    if seed == 26:
        # Empty propagated entries ignored when computing ENTITLEMENT_ESCALATION miss.
        ev_a = _register_event(1, "p1", "alpha")
        ev_b = _register_event(2, "p2", "beta")
        grant = {
            "seq": 3, "event_id": "p3", "coordinator_id": "alpha",
            "grantor_coordinator": "alpha", "grantee_coordinator": "beta",
            "kind": "GRANT_INHERITANCE",
        }
        bind = {
            "seq": 4, "event_id": "p4", "coordinator_id": "alpha",
            "kind": "BIND_ENTITLEMENT", "entitlement_key": "a:ok",
        }
        access = {
            "seq": 5, "event_id": "p5", "coordinator_id": "beta",
            "requestor_id": "alpha", "eval_target_id": "beta",
            "kind": "ACCESS_EVAL", "action": "GET",
            "has_governance_attestation": True,
            "propagated_entitlements": ["", "z:need", "a:ok"],
        }
        return _build_elwj([
            (1, 0, 0, _event_payload(ev_a)),
            (2, 0, 0, _event_payload(ev_b)),
            (3, 0, 0, _event_payload(grant)),
            (4, 0, 0, _event_payload(bind)),
            (5, 0, 0, _event_payload(access)),
        ])
    if seed == 27:
        # Exactly 5120-byte payload must be accepted (not LEN_OVERFLOW).
        base = {
            "seq": 1,
            "event_id": "cap",
            "coordinator_id": "alpha",
            "kind": "REGISTER_COORDINATOR",
            "privilege_tier": "operational",
            "business_unit": "core",
            "pad": "",
        }
        payload = _event_payload(base)
        need = 5120 - len(payload)
        base["pad"] = "z" * max(0, need)
        payload = _event_payload(base)
        if len(payload) > 5120:
            base["pad"] = "z" * (len(base["pad"]) - (len(payload) - 5120))
            payload = _event_payload(base)
        assert len(payload) == 5120, len(payload)
        return _build_elwj([(1, 0, 0, payload)])
    if seed == 28:
        # Underscore mismatch that should DOMAIN_BLEED if fold is missing wrong way:
        # tenant_a vs tenantb should still bleed.
        ev_a = {
            "seq": 1, "event_id": "b1", "coordinator_id": "alpha",
            "kind": "REGISTER_COORDINATOR", "privilege_tier": "operational",
            "business_unit": "tenant_a",
        }
        ev_b = {
            "seq": 2, "event_id": "b2", "coordinator_id": "beta",
            "kind": "REGISTER_COORDINATOR", "privilege_tier": "operational",
            "business_unit": "tenant_b",
        }
        grant = {
            "seq": 3, "event_id": "b3", "coordinator_id": "alpha",
            "grantor_coordinator": "alpha", "grantee_coordinator": "beta",
            "kind": "GRANT_INHERITANCE",
        }
        access = {
            "seq": 4, "event_id": "b4", "coordinator_id": "beta",
            "requestor_id": "alpha", "eval_target_id": "beta",
            "kind": "ACCESS_EVAL", "action": "GET",
            "has_governance_attestation": True, "propagated_entitlements": [],
        }
        return _build_elwj([
            (1, 0, 0, _event_payload(ev_a)),
            (2, 0, 0, _event_payload(ev_b)),
            (3, 0, 0, _event_payload(grant)),
            (4, 0, 0, _event_payload(access)),
        ])
    if seed == 29:
        # block=false path without audit still RESTRICTED — journal alone; scenario override applied in dedicated test.
        ev_v = _register_event(1, "r1", "vend", tier="vendor")
        ev_s = _register_event(2, "r2", "sov", tier="sovereign")
        bind = {"seq": 3, "event_id": "r3", "coordinator_id": "sov", "kind": "BIND_ENTITLEMENT", "entitlement_key": "governance:admin"}
        grant = {
            "seq": 4, "event_id": "r4", "coordinator_id": "sov",
            "grantor_coordinator": "vend", "grantee_coordinator": "sov",
            "kind": "GRANT_INHERITANCE",
        }
        access = {
            "seq": 5, "event_id": "r5", "coordinator_id": "sov",
            "requestor_id": "vend", "eval_target_id": "sov",
            "kind": "ACCESS_EVAL", "action": "POST",
            "has_governance_attestation": True, "propagated_entitlements": [],
        }
        return _build_elwj([
            (1, 0, 0, _event_payload(ev_v)),
            (2, 0, 0, _event_payload(ev_s)),
            (3, 0, 0, _event_payload(bind)),
            (4, 0, 0, _event_payload(grant)),
            (5, 0, 0, _event_payload(access)),
        ])

    raise ValueError(f"unknown adversarial seed: {seed}")


def _generate_seeded_synthetic_elwj_journal(seed: int) -> bytes:
    """Deterministic pseudo-random ELWJ capture for runtime oracle sweeps."""
    import random

    rng = random.Random(seed)
    records: list[tuple[int, int, int, bytes]] = []
    record_seq = 1
    for _ in range(rng.randint(5, 9)):
        choice = rng.choice(
            ["valid", "bad_crc", "bad_json", "bad_flags", "overflow", "dup", "reserved"]
        )
        if choice == "valid":
            ev = _register_event(
                record_seq,
                f"e-{seed}-{record_seq}",
                f"coord-{seed % 5}",
                business_unit=rng.choice(["identity-core", "tenant-west", "tenant-east"]),
            )
            records.append((record_seq, 0, 0, _event_payload(ev)))
        elif choice == "bad_crc":
            payload = _event_payload(_register_event(record_seq, f"crc-{record_seq}", f"c-{seed}"))
            records.append((record_seq, 0, 0, payload))
            # overwrite checksum in builder below via manual blob append
            blob = _build_elwj(records[:-1]) if len(records) > 1 else b"ELWJ" + struct.pack("<I", 1)
            hdr = struct.pack("<I H H I", record_seq, 0, 0, len(payload))
            blob += hdr + payload + struct.pack("<I", 0xDEADBEEF)
            if rng.random() < 0.5:
                return blob + bytes([rng.randint(0, 255)] * rng.randint(1, 6))
            return blob
        elif choice == "bad_json":
            bad = b"{not-json"
            records.append((record_seq, 0, 0, bad))
        elif choice == "bad_flags":
            payload = _event_payload(_register_event(record_seq, f"fl-{record_seq}", f"f-{seed}"))
            records.append((record_seq, 0x02, 0, payload))
        elif choice == "overflow":
            oversize = b"\x00" * 5200
            records.append((record_seq, 0, 0, oversize))
        elif choice == "reserved":
            payload = _event_payload(_register_event(record_seq, f"rs-{record_seq}", f"r-{seed}"))
            records.append((record_seq, 0, 0x01, payload))
        elif choice == "dup":
            dup_seq = max(1, record_seq - 1)
            payload = _event_payload(_register_event(dup_seq, f"dup-{record_seq}", f"d-{seed}"))
            records.append((dup_seq, 0, 0, payload))
        record_seq += 1
    blob = _build_elwj(records)
    if rng.random() < 0.5:
        return blob + bytes([rng.randint(0, 255)] * rng.randint(1, 6))
    return blob


def _slice_row(report: dict[str, Any], sid: str) -> dict[str, Any]:
    return _delegation_slice_row(report, sid)


def _assert_full_slice_row_matches_oracle(row: dict[str, Any], sid: str, journal_bytes: bytes | None = None) -> None:
    scenario = json.loads((DATA_DIR / f"{sid}.json").read_text(encoding="utf-8"))
    expected = reconcile_slice(scenario, journal_bytes=journal_bytes)
    assert row == expected, sid


def _ledger_after_make(log_name: str) -> dict[str, Any]:
    REPORT_PATH.unlink(missing_ok=True)
    _run_make("run", log_name)
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def _slice_row_after_make(sid: str, log_name: str) -> dict[str, Any]:
    return _slice_row(_ledger_after_make(log_name), sid)


def _restore_baseline_ledger() -> None:
    REPORT_PATH.unlink(missing_ok=True)
    _run_make("run", "dynamic_global_restore.log")
    assert REPORT_PATH.read_bytes() == REPORT_FIRST.read_bytes()


@contextlib.contextmanager
def _swap_slice_journal(sid: str, blob: bytes):
    journal_path = DATA_DIR / sid / "inheritance_journal.elwj"
    backup = VERIFIER_DIR / f"{sid}_dynamic_backup.elwj"
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(journal_path, backup)
    try:
        journal_path.write_bytes(blob)
        yield journal_path
    finally:
        shutil.copy(backup, journal_path)


@contextlib.contextmanager
def _swap_slice_journals(overrides: dict[str, bytes]):
    backups: dict[str, Path] = {}
    try:
        for sid, blob in overrides.items():
            journal_path = DATA_DIR / sid / "inheritance_journal.elwj"
            backup = VERIFIER_DIR / f"{sid}_multi_backup.elwj"
            VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy(journal_path, backup)
            backups[sid] = backup
            journal_path.write_bytes(blob)
        yield
    finally:
        for sid, backup in backups.items():
            shutil.copy(backup, DATA_DIR / sid / "inheritance_journal.elwj")



def _run_make(target: str, log_name: str) -> None:
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["make", target],
        cwd=APP_DIR,
        capture_output=True,
        text=True,
    )
    (VERIFIER_DIR / log_name).write_text(proc.stdout + proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        pytest.fail(f"make {target} failed; see /logs/verifier/{log_name}")


@pytest.fixture(scope="session", autouse=True)
def _verifier_preflight() -> None:
    """Build delegationintegrity and snapshot first run for byte-identical rerun checks."""
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.unlink(missing_ok=True)
    for path in VERIFIER_DIR.glob("*.log"):
        path.unlink()

    _run_make("build", "build.log")
    _run_make("run", "run.log")
    if not REPORT_PATH.is_file():
        pytest.fail("delegation_integrity_snapshot.json missing after make run")
    shutil.copy(REPORT_PATH, REPORT_FIRST)

    _run_make("run", "run2.log")
    if REPORT_PATH.read_bytes() != REPORT_FIRST.read_bytes():
        pytest.fail("make run not byte-identical across consecutive invocations")






def _elwj_rejection_blob(kind: str) -> bytes:
    """Single-frame ELWJ blobs exercising one decode rejection path."""
    ev = _register_event(1, "rej", "relay-rej")
    payload = _event_payload(ev)
    if kind == "reserved":
        return _build_elwj([(1, 0, 0x01, payload)])
    if kind == "flags":
        return _build_elwj([(1, 0, 0x02, payload)])
    if kind == "len_overflow_skip":
        oversize = b"\x00" * 5200
        header = struct.pack("<I H H I", 1, 0, 0, len(oversize))
        checksum = struct.pack("<I", zlib.crc32(header + oversize) & 0xFFFFFFFF)
        return b"ELWJ" + struct.pack("<I", 1) + header + oversize + checksum
    if kind == "len_overflow_truncated":
        oversize = b"\x00" * 5200
        header = struct.pack("<I H H I", 1, 0, 0, len(oversize))
        return b"ELWJ" + struct.pack("<I", 1) + header + oversize[:100]
    if kind == "dup_seq":
        return _build_elwj([(1, 0, 0, payload), (1, 0, 0, _event_payload({**ev, "event_id": "rej2"}))])
    if kind == "bad_crc":
        return _build_elwj([(1, 0, 0, payload)])[:-4] + struct.pack("<I", 0xDEADBEEF)
    if kind == "partial_payload":
        hdr = struct.pack("<I H H I", 1, 0, 0, len(payload))
        return b"ELWJ" + struct.pack("<I", 1) + hdr + payload[: max(1, len(payload) // 2)]
    if kind == "bad_json":
        return _build_elwj([(1, 0, 0, b"{not-json")])
    if kind == "truncated_header":
        return b"ELWJ" + struct.pack("<I", 1) + b"\x01\x02\x03"
    raise ValueError(kind)


def _run_with_replaced_journal(sid: str, blob: bytes, log_name: str) -> dict[str, Any]:
    """Swap one slice inheritance_journal, run make run, return that slice row."""
    with _swap_slice_journal(sid, blob):
        return _slice_row_after_make(sid, log_name)


def _expected_full_ledger(journal_overrides: dict[str, bytes] | None = None) -> dict[str, Any]:
    """Independent full snapshot oracle with optional per-slice journal byte overrides."""
    overrides = journal_overrides or {}
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {
        "delegation_slices": [
            reconcile_slice(
                json.loads((DATA_DIR / f"{sid}.json").read_text(encoding="utf-8")),
                journal_bytes=overrides.get(sid),
            )
            for sid in catalog["delegation_slices"]
        ]
    }


def _finding_id(sid: str, entity: str, seq: int) -> str:
    return f"{sid}::{entity}::{seq:04d}"


def _resolve_bools(scenario: dict[str, Any]) -> tuple[bool, bool]:
    require = bool(scenario.get("require_attestation_on_operational", True))
    block = bool(scenario.get("block_vendor_to_sovereign", True))
    overrides = scenario.get("governance_overrides") or {}
    if "require_attestation_on_operational" in overrides:
        require = bool(overrides["require_attestation_on_operational"])
    if "block_vendor_to_sovereign" in overrides:
        block = bool(overrides["block_vendor_to_sovereign"])
    return require, block


def _trust_risk(privilege_tier: str) -> str:
    if privilege_tier == "vendor":
        return "elevated"
    if privilege_tier == "sovereign":
        return "critical"
    return "contained"


def _canonical_business_unit(raw: str) -> str:
    s = (raw or "").strip().lower().replace("_", "-")
    return s if s else "business-core"


def reconcile_slice(scenario: dict[str, Any], journal_bytes: bytes | None = None) -> dict[str, Any]:
    """Independent replay implementing /app/provenance_charters/DELEGATION_LINEAGE_CORRUPTION_RULES.md from bundled inheritance_journal."""
    sid = scenario["delegation_slice_id"]
    if journal_bytes is None:
        cap_stats, events = decode_inheritance_journal(DATA_DIR / sid / "inheritance_journal.elwj")
    else:
        cap_stats, events = decode_inheritance_journal_bytes(journal_bytes)
    require_attestation, block_vendor = _resolve_bools(scenario)
    coordinators: dict[str, dict[str, Any]] = {}
    tombstones: set[str] = set()
    edges: set[tuple[str, str]] = set()
    findings: list[dict[str, Any]] = []
    dup_skipped = 0
    seen_event: set[str] = set()
    priv_flagged: set[str] = set()
    max_seq = 0

    events = sorted(
        events,
        key=lambda e: (e["seq"], e.get("coordinator_id", ""), e.get("event_id", "")),
    )

    def add_finding(entity: str, kind: str, seq: int, action: str = "", detail: str = "") -> None:
        findings.append(
            {
                "finding_id": _finding_id(sid, entity, seq),
                "entity_id": entity,
                "kind": kind,
                "event_seq": seq,
                "action": action,
                "detail": detail,
            }
        )

    def has_edge(frm: str, to: str) -> bool:
        return (frm, to) in edges

    def first_missing(caps: set[str], propagated: list[str]) -> str:
        missing = sorted(p for p in propagated if p and p not in caps)
        return missing[0] if missing else ""

    def remove_edges_for(pid: str) -> None:
        nonlocal edges
        edges = {(frm, to) for frm, to in edges if frm != pid and to != pid}

    for ev in events:
        seq = ev["seq"]
        max_seq = max(max_seq, seq)
        kind = ev["kind"]
        id_key = (ev.get("event_id") or "").strip()
        if id_key:
            if id_key in seen_event:
                dup_skipped += 1
                continue
            seen_event.add(id_key)

        if kind == "REGISTER_COORDINATOR":
            svc = ev["coordinator_id"]
            if svc in tombstones:
                add_finding(svc, "RESURRECTED_ENTITLEMENT", seq)
                continue
            if svc in coordinators:
                add_finding(svc, "DUPLICATE_COORDINATOR", seq)
                continue
            coordinators[svc] = {
                "privilege_tier": ev["privilege_tier"],
                "tenant": _canonical_business_unit(ev.get("business_unit", "")),
                "caps": set(),
            }
            continue

        if kind == "RETIRE_COORDINATOR_SCOPE":
            svc = ev["coordinator_id"]
            if svc not in coordinators:
                add_finding(svc, "UNKNOWN_COORDINATOR", seq, detail=kind)
                continue
            del coordinators[svc]
            tombstones.add(svc)
            remove_edges_for(svc)
            continue

        if kind == "GRANT_INHERITANCE":
            frm, to = ev["grantor_coordinator"], ev["grantee_coordinator"]
            if frm not in coordinators:
                add_finding(frm, "UNKNOWN_COORDINATOR", seq, detail=kind)
                continue
            if to not in coordinators:
                add_finding(to, "UNKNOWN_TARGET", seq, detail=kind)
                continue
            if (frm, to) in edges:
                add_finding(to, "DUPLICATE_INHERITANCE", seq, detail=frm)
                continue
            edges.add((frm, to))
            continue

        if kind == "REVOKE_INHERITANCE":
            frm, to = ev["grantor_coordinator"], ev["grantee_coordinator"]
            if frm not in coordinators:
                add_finding(frm, "UNKNOWN_COORDINATOR", seq, detail=kind)
                continue
            if to not in coordinators:
                add_finding(to, "UNKNOWN_TARGET", seq, detail=kind)
                continue
            edges.discard((frm, to))
            continue

        if kind == "BIND_ENTITLEMENT":
            svc = ev["coordinator_id"]
            if svc not in coordinators:
                add_finding(svc, "UNKNOWN_COORDINATOR", seq, detail=kind)
                continue
            coordinators[svc]["caps"].add(ev["entitlement_key"])
            continue

        if kind == "ACCESS_EVAL":
            caller, callee = ev["requestor_id"], ev["eval_target_id"]
            action = ev.get("action", "")
            propagated = ev.get("propagated_entitlements") or []
            if callee not in coordinators:
                add_finding(callee, "UNKNOWN_TARGET", seq, action=action, detail=kind)
                continue
            if caller not in coordinators:
                add_finding(caller, "UNKNOWN_COORDINATOR", seq, action=action, detail=kind)
                continue
            if not has_edge(caller, callee):
                add_finding(callee, "UNTRUSTED_INHERITANCE", seq, action=action, detail=caller)
                continue
            if coordinators[caller]["tenant"] != coordinators[callee]["tenant"]:
                add_finding(callee, "DOMAIN_BLEED", seq, action=action, detail=caller)
                continue
            if (
                coordinators[caller]["privilege_tier"] == "vendor"
                and coordinators[callee]["privilege_tier"] == "sovereign"
            ):
                has_audit = "governance:audit" in coordinators[callee]["caps"]
                if block_vendor or not has_audit:
                    add_finding(caller, "RESTRICTED_TIER", seq, action=action, detail=callee)
                    continue
            if require_attestation and coordinators[callee]["privilege_tier"] == "operational" and not ev.get("has_governance_attestation"):
                add_finding(callee, "UNATTESTED_ACCESS", seq, action=action)
                continue
            miss = first_missing(coordinators[caller]["caps"], propagated)
            if miss:
                key = f"{caller}::{miss}"
                if key not in priv_flagged:
                    priv_flagged.add(key)
                    add_finding(caller, "ENTITLEMENT_ESCALATION", seq, action=action, detail=miss)
            orig = ev.get("provenance_requestor") or ""
            if orig and orig != caller:
                miss2 = first_missing(coordinators[caller]["caps"], propagated)
                if miss2:
                    add_finding(orig, "LATERAL_GHOSTING", seq, action=action, detail=miss2)

    audit_seq = max_seq + 1
    mesh_flagged: set[str] = set()
    open_flagged: set[str] = set()

    for frm, to in sorted(edges):
        if frm not in coordinators or to not in coordinators:
            continue
        if coordinators[frm]["privilege_tier"] == "vendor" and coordinators[to]["privilege_tier"] == "operational":
            mkey = f"{frm}::{to}"
            if mkey not in mesh_flagged and not has_edge(to, frm):
                mesh_flagged.add(mkey)
                add_finding(to, "INHERITANCE_ASYMMETRY", audit_seq, detail=frm)

    for svc_id in sorted(coordinators):
        st = coordinators[svc_id]
        if st["privilege_tier"] != "sovereign":
            continue
        if "governance:audit" in st["caps"]:
            continue
        vendors = sorted(
            frm
            for frm, to in edges
            if to == svc_id and frm in coordinators and coordinators[frm]["privilege_tier"] == "vendor"
        )
        if vendors and svc_id not in open_flagged:
            open_flagged.add(svc_id)
            add_finding(svc_id, "OPEN_GHOST_PATH", audit_seq, detail=vendors[0])

    for svc_id in sorted(coordinators):
        if coordinators[svc_id]["privilege_tier"] == "sovereign" and "governance:admin" not in coordinators[svc_id]["caps"]:
            add_finding(svc_id, "SOVEREIGN_UNBOUND", audit_seq)

    edge_out = [
        {"grantor_coordinator": frm, "grantee_coordinator": to}
        for frm, to in sorted(edges)
    ]
    out_coordinators = [
        {
            "coordinator_id": svc_id,
            "privilege_tier": coordinators[svc_id]["privilege_tier"],
            "entitlement_bindings": sorted(coordinators[svc_id]["caps"]),
            "delegation_poison_risk": _trust_risk(coordinators[svc_id]["privilege_tier"]),
        }
        for svc_id in sorted(coordinators)
    ]

    findings.sort(key=lambda f: f["finding_id"])
    inheritance_journal = {k: cap_stats[k] for k in INHERITANCE_JOURNAL_KEY_ORDER}
    return {
        "delegation_slice_id": sid,
        "status": "VALID" if not findings else "INVALID",
        "duplicate_events_skipped": dup_skipped,
        "inheritance_journal": inheritance_journal,
        "inheritance_edges": edge_out,
        "coordinators": out_coordinators,
        "findings": findings,
    }


def _build_ledger() -> dict[str, Any]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {
        "delegation_slices": [
            reconcile_slice(json.loads((DATA_DIR / f"{sid}.json").read_text(encoding="utf-8")))
            for sid in catalog["delegation_slices"]
        ]
    }


def _delegation_slice_row(ledger: dict[str, Any], delegation_slice_id: str) -> dict[str, Any]:
    for row in ledger["delegation_slices"]:
        if row["delegation_slice_id"] == delegation_slice_id:
            return row
    raise KeyError(delegation_slice_id)


@pytest.fixture(scope="module")
def ledger_bytes() -> bytes:
    assert REPORT_PATH.is_file()
    return REPORT_PATH.read_bytes()


@pytest.fixture(scope="module")
def ledger() -> dict[str, Any]:
    assert REPORT_PATH.is_file(), f"missing {REPORT_PATH}"
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def expected_ledger() -> dict[str, Any]:
    return _build_ledger()


def _report_digest(ledger: dict[str, Any]) -> str:
    payload = json.dumps(ledger, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _assert_no_json_null(value: Any, path: str = "ledger") -> None:
    if value is None:
        raise AssertionError(f"null at {path}")
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_no_json_null(item, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            _assert_no_json_null(item, f"{path}[{idx}]")


def _assert_schema_sort_order(row: dict[str, Any]) -> None:
    edges = row["inheritance_edges"]
    assert edges == sorted(edges, key=lambda e: (e["grantor_coordinator"], e["grantee_coordinator"]))
    svc_ids = [s["coordinator_id"] for s in row["coordinators"]]
    assert svc_ids == sorted(svc_ids)
    for svc in row["coordinators"]:
        assert svc["entitlement_bindings"] == sorted(svc["entitlement_bindings"])
    finding_ids = [f["finding_id"] for f in row["findings"]]
    assert finding_ids == sorted(finding_ids)



def test_full_reconcile_equivalence_invariant(
    ledger: dict[str, Any], expected_ledger: dict[str, Any]
) -> None:
    """Every catalog slice must match the independent rules-engine replay with no drift."""
    assert ledger == expected_ledger
    kinds = {f["kind"] for row in ledger["delegation_slices"] for f in row["findings"]}
    assert kinds == FINDING_KINDS
    assert len(ledger["delegation_slices"]) == 28
    assert _report_digest(ledger) == _report_digest(expected_ledger)


def test_solution_contract_integrity(ledger: dict[str, Any]) -> None:
    """Bundled immutability, catalog order, schema keys, compact JSON, path literals, determinism."""
    for path in APP_DIR.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(APP_DIR).as_posix()
        if rel.startswith(("cmd/", "internal/", "build/")):
            continue
        assert rel in ORIGINAL_PROTECTED_SHA256, f"untracked path {rel}"
        assert _sha256_file(path) == ORIGINAL_PROTECTED_SHA256[rel], f"modified {rel}"

    expected_ids = [f"delegation_slice_{i:02d}" for i in range(1, 29)]
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    assert catalog["delegation_slices"] == expected_ids
    assert [row["delegation_slice_id"] for row in ledger["delegation_slices"]] == expected_ids

    allowed_top = {
        "cmd", "internal", "build", "provenance_charters",
        "delegation_federation_slices", "go.mod", "go.sum", "Makefile",
    }
    for entry in APP_DIR.iterdir():
        assert entry.name in allowed_top, f"unexpected /app/{entry.name}"

    assert BINARY.is_file() and not BINARY.is_symlink()
    assert REPORT_PATH.is_file() and not REPORT_PATH.is_symlink()
    assert {p.name for p in (APP_DIR / "build").iterdir()} == {
        "delegationintegrity", "delegation_integrity_snapshot.json"
    }
    text = MAIN_GO.read_text(encoding="utf-8")
    assert 'fixtureRoot := "/app/delegation_federation_slices"' in text
    assert 'outPath := "/app/build/delegation_integrity_snapshot.json"' in text

    for row in ledger["delegation_slices"]:
        assert list(row.keys()) == SLICE_KEY_ORDER
        assert list(row["inheritance_journal"].keys()) == INHERITANCE_JOURNAL_KEY_ORDER
        _assert_schema_sort_order(row)
        for finding in row["findings"]:
            assert FINDING_ID_RE.match(finding["finding_id"])
            assert finding["kind"] in FINDING_KINDS

    _assert_no_json_null(ledger)
    raw = REPORT_PATH.read_bytes()
    assert raw.endswith(b"\n") and b": " not in raw and b", " not in raw
    assert b"null" not in raw
    canonical = json.dumps(ledger, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
    assert raw == canonical
    assert REPORT_FIRST.is_file() and raw == REPORT_FIRST.read_bytes()


@contextlib.contextmanager
def _swap_slice_scenario(sid: str, scenario: dict[str, Any]):
    path = DATA_DIR / f"{sid}.json"
    backup = VERIFIER_DIR / f"{sid}_scenario_backup.json"
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(path, backup)
    try:
        path.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")
        yield path
    finally:
        shutil.copy(backup, path)


def test_perturbed_inheritance_journal_changes_report_then_restores(ledger: dict[str, Any]) -> None:
    """Anti-cheat: perturbing a bundled journal byte must change output then restore baseline."""
    sid = "delegation_slice_01"
    journal = DATA_DIR / sid / "inheritance_journal.elwj"
    clean = VERIFIER_DIR / f"{sid}_perturb_clean.elwj"
    shutil.copy(journal, clean)
    baseline = REPORT_PATH.read_bytes()
    try:
        data = bytearray(journal.read_bytes())
        data[20] ^= 0xFF
        journal.write_bytes(data)
        REPORT_PATH.unlink(missing_ok=True)
        _run_make("run", "perturb_run.log")
        assert REPORT_PATH.read_bytes() != baseline
    finally:
        shutil.copy(clean, journal)
        _restore_baseline_ledger()


@pytest.mark.parametrize("seed", [7, 9, 18, 24, 25, 26, 27, 28])
def test_dynamic_compound_adversarial_matrix_matches_oracle(seed: int) -> None:
    """Seeded compound ELWJ captures must match independent oracle through delegationintegrity."""
    sid = DYNAMIC_SWAP_SLICE
    scenario = json.loads((DATA_DIR / f"{sid}.json").read_text(encoding="utf-8"))
    blob = _compound_adversarial_elwj_blob(seed)
    expected = reconcile_slice(scenario, journal_bytes=blob)
    row = _run_with_replaced_journal(sid, blob, f"dynamic_matrix_{seed}.log")
    assert row == expected
    _restore_baseline_ledger()


def test_hard_underscore_business_unit_fold_prevents_domain_bleed() -> None:
    """Tenant_A and tenant-a must canonicalize equal; missing underscore-fold causes DOMAIN_BLEED."""
    sid = DYNAMIC_SWAP_SLICE
    scenario = json.loads((DATA_DIR / f"{sid}.json").read_text(encoding="utf-8"))
    blob = _compound_adversarial_elwj_blob(24)
    expected = reconcile_slice(scenario, journal_bytes=blob)
    assert expected["status"] == "VALID"
    assert not any(f["kind"] == "DOMAIN_BLEED" for f in expected["findings"])
    row = _run_with_replaced_journal(sid, blob, "hard_underscore_fold.log")
    assert row == expected
    _restore_baseline_ledger()


def test_hard_whitespace_event_id_dedup_identity_through_binary() -> None:
    """Whitespace-only event_ids must not dedup; trimmed non-empty duplicates must."""
    sid = DYNAMIC_SWAP_SLICE
    scenario = json.loads((DATA_DIR / f"{sid}.json").read_text(encoding="utf-8"))
    blob = _compound_adversarial_elwj_blob(25)
    expected = reconcile_slice(scenario, journal_bytes=blob)
    assert expected["duplicate_events_skipped"] == 1
    assert expected["status"] == "VALID"
    row = _run_with_replaced_journal(sid, blob, "hard_ws_event_id.log")
    assert row == expected
    _restore_baseline_ledger()


def test_hard_empty_propagated_entitlement_ignored_for_escalation() -> None:
    """Empty strings in propagated_entitlements must not become ENTITLEMENT_ESCALATION detail."""
    sid = DYNAMIC_SWAP_SLICE
    scenario = json.loads((DATA_DIR / f"{sid}.json").read_text(encoding="utf-8"))
    blob = _compound_adversarial_elwj_blob(26)
    expected = reconcile_slice(scenario, journal_bytes=blob)
    assert any(f["kind"] == "ENTITLEMENT_ESCALATION" and f["detail"] == "z:need" for f in expected["findings"])
    assert not any(f["kind"] == "ENTITLEMENT_ESCALATION" and f["detail"] == "" for f in expected["findings"])
    row = _run_with_replaced_journal(sid, blob, "hard_empty_propagated.log")
    assert row == expected
    _restore_baseline_ledger()


def test_hard_payload_len_exactly_5120_accepted_not_overflow() -> None:
    """payload_len == 5120 must validate; agents using >= 5120 as overflow fail this case."""
    sid = MATRIX_SWAP_SLICE
    scenario = json.loads((DATA_DIR / f"{sid}.json").read_text(encoding="utf-8"))
    blob = _compound_adversarial_elwj_blob(27)
    expected = reconcile_slice(scenario, journal_bytes=blob)
    assert expected["inheritance_journal"]["records_valid"] == 1
    assert expected["inheritance_journal"]["records_rejected"] == 0
    assert expected["inheritance_journal"]["payload_bytes"] == 5120
    row = _run_with_replaced_journal(sid, blob, "hard_cap_5120.log")
    assert row == expected
    _restore_baseline_ledger()


def test_hard_restricted_tier_survives_false_block_without_governance_audit() -> None:
    """When block_vendor_to_sovereign is overridden false, missing callee governance:audit still RESTRICTED."""
    sid = "delegation_slice_11"
    scenario = {
        "delegation_slice_id": sid,
        "block_vendor_to_sovereign": True,
        "governance_overrides": {"block_vendor_to_sovereign": False},
    }
    blob = _compound_adversarial_elwj_blob(29)
    expected = reconcile_slice(scenario, journal_bytes=blob)
    assert any(f["kind"] == "RESTRICTED_TIER" for f in expected["findings"])
    with _swap_slice_scenario(sid, scenario):
        row = _run_with_replaced_journal(sid, blob, "hard_restricted_override.log")
        assert row == expected
    _restore_baseline_ledger()


def test_hard_restricted_bypass_requires_governance_audit_on_sovereign() -> None:
    """False block override + sovereign governance:audit must allow vendor→sovereign ACCESS_EVAL."""
    sid = "delegation_slice_11"
    scenario = {
        "delegation_slice_id": sid,
        "governance_overrides": {"block_vendor_to_sovereign": False},
    }
    ev_v = _register_event(1, "ok1", "vend", tier="vendor")
    ev_s = _register_event(2, "ok2", "sov", tier="sovereign")
    bind_a = {"seq": 3, "event_id": "ok3", "coordinator_id": "sov", "kind": "BIND_ENTITLEMENT", "entitlement_key": "governance:audit"}
    bind_b = {"seq": 4, "event_id": "ok4", "coordinator_id": "sov", "kind": "BIND_ENTITLEMENT", "entitlement_key": "governance:admin"}
    grant = {
        "seq": 5, "event_id": "ok5", "coordinator_id": "sov",
        "grantor_coordinator": "vend", "grantee_coordinator": "sov",
        "kind": "GRANT_INHERITANCE",
    }
    access = {
        "seq": 6, "event_id": "ok6", "coordinator_id": "sov",
        "requestor_id": "vend", "eval_target_id": "sov",
        "kind": "ACCESS_EVAL", "action": "GET",
        "has_governance_attestation": True, "propagated_entitlements": [],
    }
    blob = _build_elwj([
        (1, 0, 0, _event_payload(ev_v)),
        (2, 0, 0, _event_payload(ev_s)),
        (3, 0, 0, _event_payload(bind_a)),
        (4, 0, 0, _event_payload(bind_b)),
        (5, 0, 0, _event_payload(grant)),
        (6, 0, 0, _event_payload(access)),
    ])
    expected = reconcile_slice(scenario, journal_bytes=blob)
    assert expected["status"] == "VALID"
    assert not any(f["kind"] == "RESTRICTED_TIER" for f in expected["findings"])
    with _swap_slice_scenario(sid, scenario):
        row = _run_with_replaced_journal(sid, blob, "hard_restricted_bypass_ok.log")
        assert row == expected
    _restore_baseline_ledger()


def test_hard_domain_bleed_still_fires_after_underscore_fold() -> None:
    """tenant_a vs tenant_b remain distinct after underscore fold and must DOMAIN_BLEED."""
    sid = DYNAMIC_SWAP_SLICE
    scenario = json.loads((DATA_DIR / f"{sid}.json").read_text(encoding="utf-8"))
    blob = _compound_adversarial_elwj_blob(28)
    expected = reconcile_slice(scenario, journal_bytes=blob)
    assert any(f["kind"] == "DOMAIN_BLEED" for f in expected["findings"])
    row = _run_with_replaced_journal(sid, blob, "hard_domain_bleed_fold.log")
    assert row == expected
    _restore_baseline_ledger()


def test_go_len_overflow_before_dup_seq_when_both_apply_through_binary() -> None:
    """LEN_OVERFLOW must win over DUP_SEQ when both would apply on the same frame."""
    sid = DYNAMIC_SWAP_SLICE
    scenario = json.loads((DATA_DIR / f"{sid}.json").read_text(encoding="utf-8"))
    blob = _compound_adversarial_elwj_blob(18)
    expected = reconcile_slice(scenario, journal_bytes=blob)
    row = _run_with_replaced_journal(sid, blob, "go_len_before_dup.log")
    assert row["inheritance_journal"] == expected["inheritance_journal"]
    _restore_baseline_ledger()


def test_dynamic_dual_slice_mutation_full_report_equivalence(ledger: dict[str, Any]) -> None:
    """Mutating two bundled journals in one run must match independent full-report oracle."""
    overrides = {
        DYNAMIC_SWAP_SLICE: _compound_adversarial_elwj_blob(24),
        MATRIX_SWAP_SLICE: _compound_adversarial_elwj_blob(26),
    }
    expected = _expected_full_ledger(overrides)
    with _swap_slice_journals(overrides):
        actual = _ledger_after_make("dynamic_dual_slice.log")
        assert actual == expected
        assert actual != ledger
    _restore_baseline_ledger()


def test_runtime_thirty_seed_oracle_sweep(ledger_bytes: bytes) -> None:
    """Thirty seeded synthetic journals must each match independent oracle replay through the binary."""
    sid = MATRIX_SWAP_SLICE
    scenario = json.loads((DATA_DIR / f"{sid}.json").read_text(encoding="utf-8"))
    journal_path = DATA_DIR / sid / "inheritance_journal.elwj"
    backup = VERIFIER_DIR / f"{sid}_seed30_backup.elwj"
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(journal_path, backup)
    try:
        for seed in range(3, 63, 2):
            synthetic = _generate_seeded_synthetic_elwj_journal(seed)
            expected = reconcile_slice(scenario, journal_bytes=synthetic)
            journal_path.write_bytes(synthetic)
            REPORT_PATH.unlink(missing_ok=True)
            _run_make("run", f"seed30_{seed}.log")
            got = _slice_row(json.loads(REPORT_PATH.read_text(encoding="utf-8")), sid)
            assert got == expected, f"seed {seed} mismatch"
    finally:
        shutil.copy(backup, journal_path)
        REPORT_PATH.unlink(missing_ok=True)
        _run_make("run", "seed30_restore.log")
        assert REPORT_PATH.read_bytes() == ledger_bytes


def test_dynamic_shuffled_roll_order_preserves_snapshot_slice_sequence(ledger: dict[str, Any]) -> None:
    """Report slice order must follow federation_slice_roll.json catalog order, not directory listing."""
    original = CATALOG_PATH.read_text(encoding="utf-8")
    try:
        catalog = json.loads(original)
        shuffled = list(reversed(catalog["delegation_slices"]))
        catalog["delegation_slices"] = shuffled
        CATALOG_PATH.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
        got = _ledger_after_make("roll_shuffle.log")
        assert [row["delegation_slice_id"] for row in got["delegation_slices"]] == shuffled
    finally:
        CATALOG_PATH.write_text(original, encoding="utf-8")
        _restore_baseline_ledger()


def test_dynamic_unsupported_format_version_aborts_run() -> None:
    """Unsupported ELWJ format_version must abort decode instead of emitting partial snapshot."""
    sid = DYNAMIC_SWAP_SLICE
    blob = b"ELWJ" + struct.pack("<I", 3)
    with _swap_slice_journal(sid, blob):
        REPORT_PATH.unlink(missing_ok=True)
        proc = subprocess.run(["make", "run"], cwd=APP_DIR, capture_output=True, text=True)
        assert proc.returncode != 0, proc.stdout + proc.stderr
        assert not REPORT_PATH.exists()
    _restore_baseline_ledger()


def test_missing_catalog_aborts_without_partial_report() -> None:
    """Missing roll file must abort and must not emit a partial snapshot."""
    baseline = REPORT_PATH.read_bytes()
    tmp = VERIFIER_DIR / "roll_missing_backup.json"
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(CATALOG_PATH, tmp)
    try:
        CATALOG_PATH.unlink()
        REPORT_PATH.unlink(missing_ok=True)
        proc = subprocess.run(["make", "run"], cwd=APP_DIR, capture_output=True, text=True)
        assert proc.returncode != 0, proc.stdout + proc.stderr
        assert not REPORT_PATH.exists()
    finally:
        shutil.copy(tmp, CATALOG_PATH)
        REPORT_PATH.unlink(missing_ok=True)
        _run_make("run", "roll_restore_after_missing.log")
        assert REPORT_PATH.read_bytes() == baseline


def test_path_traps_symlink_cwd_readonly_preserve_byte_identity() -> None:
    """Symlink exec, alternate cwd, and read-only fixtures must preserve absolute-path byte identity."""
    import os
    import stat

    baseline = REPORT_PATH.read_bytes()

    link = VERIFIER_DIR / "delegationintegrity-symlink"
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to(BINARY)
    REPORT_PATH.unlink(missing_ok=True)
    proc = subprocess.run([str(link)], cwd=APP_DIR, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert REPORT_PATH.read_bytes() == baseline

    REPORT_PATH.unlink(missing_ok=True)
    proc = subprocess.run(["make", "-C", str(APP_DIR), "run"], cwd="/tmp", capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert REPORT_PATH.read_bytes() == baseline

    REPORT_PATH.unlink(missing_ok=True)
    proc = subprocess.run([str(BINARY)], cwd="/tmp", capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert REPORT_PATH.read_bytes() == baseline

    def _chmod_tree(root: Path, mode: int) -> None:
        for item in root.rglob("*"):
            os.chmod(item, mode)
        os.chmod(root, mode)

    original_mode = stat.S_IMODE(os.stat(DATA_DIR).st_mode)
    try:
        _chmod_tree(DATA_DIR, original_mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)
        REPORT_PATH.unlink(missing_ok=True)
        _run_make("run", "readonly_data.log")
        assert REPORT_PATH.read_bytes() == baseline
    finally:
        _chmod_tree(DATA_DIR, original_mode | stat.S_IWUSR)


@pytest.mark.parametrize("slice_id,required_kinds", sorted(SLICE_FINDING_REQUIREMENTS.items()))
def test_slice_contract_matrix_matches_oracle(
    ledger: dict[str, Any],
    slice_id: str,
    required_kinds: frozenset[str],
) -> None:
    """Every bundled slice must satisfy class contracts and the independent oracle through the binary."""
    row = _slice_row(ledger, slice_id)
    _assert_full_slice_row_matches_oracle(row, slice_id)
    kinds = {finding["kind"] for finding in row["findings"]}
    assert required_kinds <= kinds
    if not required_kinds and slice_id not in SLICE_SPOT_CHECKS:
        assert row["status"] == "VALID"
        assert kinds == set()
    spot = SLICE_SPOT_CHECKS.get(slice_id)
    if spot is not None:
        assert spot(row), slice_id


@pytest.mark.parametrize(
    "seed,check",
    [
        (24, lambda row: row["status"] == "VALID" and not any(f["kind"] == "DOMAIN_BLEED" for f in row["findings"])),
        (25, lambda row: row["duplicate_events_skipped"] == 1 and row["status"] == "VALID"),
        (26, lambda row: any(f["kind"] == "ENTITLEMENT_ESCALATION" and f["detail"] == "z:need" for f in row["findings"])),
        (27, lambda row: row["inheritance_journal"]["payload_bytes"] == 5120 and row["inheritance_journal"]["records_valid"] == 1),
        (28, lambda row: any(f["kind"] == "DOMAIN_BLEED" for f in row["findings"])),
    ],
)
def test_runtime_replay_semantics_through_binary(seed: int, check: Any) -> None:
    """Synthetic compound journals must exercise the new hard replay semantics through make run."""
    sid = DYNAMIC_SWAP_SLICE if seed != 27 else MATRIX_SWAP_SLICE
    scenario = json.loads((DATA_DIR / f"{sid}.json").read_text(encoding="utf-8"))
    blob = _compound_adversarial_elwj_blob(seed)
    expected = reconcile_slice(scenario, journal_bytes=blob)
    assert check(expected), seed
    row = _run_with_replaced_journal(sid, blob, f"runtime_semantics_{seed}.log")
    assert row == expected
    _restore_baseline_ledger()

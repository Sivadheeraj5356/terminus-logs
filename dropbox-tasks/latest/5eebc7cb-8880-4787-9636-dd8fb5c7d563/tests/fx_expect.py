#!/usr/bin/env python3
"""Verifier-side digest helpers aligned with footer_contract.md and sync_record_contract.json."""

from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path

import jsonschema


class _CaseBind:
    __slots__ = (
        "rows",
        "cross",
        "g1",
        "g2",
        "cross_seed",
        "case_spec",
        "footer_view",
        "authority",
        "projection",
        "blob",
    )

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

ROOT = Path("/app/environment")
JOURNAL = ROOT / "payload" / "ring_seg.bin"


def _read_bytes(rel: str) -> bytes:
    return (ROOT / rel).read_bytes()


def _read_json(rel: str) -> dict:
    with (ROOT / rel).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _parse_footer(raw: bytes) -> dict:
    if raw[:4] != b"PQX1":
        raise ValueError("bad magic")
    off = struct.unpack("<I", raw[4:8])[0]
    pos = off
    n_keys = raw[pos]
    pos += 1
    keys = []
    for _ in range(n_keys):
        keys.append(raw[pos : pos + 16])
        pos += 16
    n_grp = raw[pos]
    pos += 1
    groups = []
    for _ in range(n_grp):
        groups.append(
            {
                "grp": raw[pos],
                "slot": raw[pos + 1],
                "seed": struct.unpack("<I", raw[pos + 2 : pos + 6])[0],
            }
        )
        pos += 6
    chunks = []
    if pos < len(raw):
        n_chunks = raw[pos]
        pos += 1
        for _ in range(n_chunks):
            chunks.append(
                {
                    "grp": raw[pos],
                    "off": struct.unpack("<I", raw[pos + 1 : pos + 5])[0],
                    "ln": struct.unpack("<I", raw[pos + 5 : pos + 9])[0],
                }
            )
            pos += 9
    return {"keys": keys, "groups": groups, "chunks": chunks}


def _load_journal() -> list[dict]:
    raw = JOURNAL.read_bytes()
    if raw[:4] != b"EJ01":
        raise ValueError("bad journal magic")
    segs = []
    pos = 4
    while pos + 20 <= len(raw):
        body = raw[pos : pos + 16]
        crc_want = struct.unpack("<I", raw[pos + 16 : pos + 20])[0]
        crc_have = zlib.crc32(body) & 0xFFFFFFFF
        if crc_want == crc_have:
            epoch_id, grp, key_slot = struct.unpack_from("<IBB", body, 0)
            aad_seed, aad_epoch = struct.unpack_from("<II", body, 6)
            segs.append(
                {
                    "epoch_id": epoch_id,
                    "grp": grp,
                    "key_slot": key_slot,
                    "aad_seed": aad_seed,
                    "aad_epoch": aad_epoch,
                }
            )
        pos += 20
    return segs


def _project_epoch(epoch_id: int) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for s in _load_journal():
        if s["epoch_id"] == epoch_id:
            out[s["grp"]] = s
    return out


def _key_material(keys: list[bytes]) -> bytes:
    return b"".join(keys)


def _lane_idx(table: dict | None, grp: int) -> int:
    if not table:
        return grp
    for lane in table.get("lanes", []):
        if lane["grp"] == grp:
            return lane["idx"]
    return grp


def _resolve_key(key_mat: bytes, grp: int, table: dict | None) -> bytes:
    idx = _lane_idx(table, grp)
    start = idx * 16
    return key_mat[start : start + 16]


def _seed_bytes(seed: int, base: list[int]) -> bytes:
    buf = struct.pack("<I", seed)
    buf += bytes(v & 0xFF for v in base)
    return buf


def _rotate_aad(seed: bytes, grp: int, lane: int) -> bytes:
    rot = (grp * lane + lane) % len(seed)
    if rot == 0:
        rot = 1
    out = bytes(seed[(i + rot) % len(seed)] for i in range(len(seed)))
    mix = struct.pack("<II", grp, lane)
    return bytes(out[i] ^ mix[i % 8] for i in range(len(out)))


def _aad_hex(aad: bytes) -> str:
    return aad.hex()


def _row_hex(grp: int, key_idx: int, aad_hex: str) -> str:
    material = f"{grp}|{key_idx}|{aad_hex}".encode()
    return hashlib.sha256(material).hexdigest()[:12]


def _cross_aad(a: str, b: str, seed: int = 0) -> str:
    material = f"G|{a}|{b}"
    if seed:
        material += f"|{seed}"
    return hashlib.sha256(material.encode()).hexdigest()


def _prefix8(aad_hex: str) -> str:
    return aad_hex[:8]


def record_digest(doc: dict) -> str:
    lines = []
    for row in doc.get("bind_rows", []):
        lines.append(
            f"B|{row['grp']}|{row['key_idx']}|{row['aad_hex']}|{row['row_hex']}"
        )
    if doc.get("cross_aad_digest"):
        lines.append(f"C|{doc['cross_aad_digest']}")
    if doc.get("part_sig"):
        lines.append(f"P|{doc['part_sig']}")
    meta = doc["run_meta"]
    lines.append(f"M|{meta['case_id']}|{meta['phase']}")
    lines.sort()
    body = "\n".join(lines) + "\n"
    return hashlib.sha256(body.encode()).hexdigest()


def stable_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_record(doc: dict, schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)


def _merge_authority(base: dict, sidecar: dict | None, inline: list | None) -> dict:
    cur = {
        "lanes": list(base.get("lanes", [])),
        "cross_seed": int(base.get("cross_seed", 0) or 0),
        "aad_base": list(base.get("aad_base") or [1, 2, 3, 4]),
    }
    if sidecar is not None:
        cur = {
            "lanes": list(sidecar.get("lanes", [])),
            "cross_seed": int(sidecar.get("cross_seed", 0) or 0),
            "aad_base": list(sidecar.get("aad_base") or [1, 2, 3, 4]),
        }
    if inline:
        cur = {
            "lanes": list(inline),
            "cross_seed": cur["cross_seed"],
            "aad_base": list(cur["aad_base"] or [1, 2, 3, 4]),
        }
    return cur


def _apply_journal_slots(table: dict, proj: dict[int, dict]) -> None:
    for lane in table["lanes"]:
        if lane["grp"] in proj:
            lane["idx"] = proj[lane["grp"]]["key_slot"]
    have = {lane["grp"] for lane in table["lanes"]}
    for grp, s in proj.items():
        if grp not in have:
            table["lanes"].append({"grp": grp, "idx": s["key_slot"]})


def _effective_lane(spec: dict, proj: dict[int, dict], grp: int) -> int:
    if spec.get("aad_lane"):
        return int(spec["aad_lane"])
    if grp in proj and proj[grp]["aad_epoch"]:
        return int(proj[grp]["aad_epoch"])
    return 1


def _bind_case(case_id: str) -> _CaseBind:
    spec = next(e for e in _read_json("payload/cases.json")["entries"] if e["id"] == case_id)
    raw = _read_bytes(spec["blob"])
    view = _parse_footer(raw)
    base = {
        "lanes": [{"grp": g["grp"], "idx": g["slot"]} for g in view["groups"]],
        "aad_base": [1, 2, 3, 4],
        "cross_seed": 0,
    }
    sidecar = None
    if spec.get("sidecar"):
        sidecar = _read_json(spec["sidecar"])
    table = _merge_authority(base, sidecar, spec.get("lanes"))
    proj = _project_epoch(int(spec.get("epoch", 0) or 0)) if spec.get("epoch") else {}
    if not spec.get("lanes"):
        _apply_journal_slots(table, proj)
    key_mat = _key_material(view["keys"])
    rows = []
    g1 = g2 = ""
    for g in view["groups"]:
        grp = g["grp"]
        _resolve_key(key_mat, grp, table)
        lane = _effective_lane(spec, proj, grp)
        seed = _seed_bytes(g["seed"], table.get("aad_base", [1, 2, 3, 4]))
        aad = _rotate_aad(seed, grp, lane)
        ahex = _aad_hex(aad)
        kidx = _lane_idx(table, grp)
        rhex = _row_hex(grp, kidx, ahex)
        rows.append({"grp": grp, "key_idx": kidx, "aad_hex": ahex, "row_hex": rhex})
        if grp == 1:
            g1 = _prefix8(ahex)
        if grp == 2:
            g2 = _prefix8(ahex)
    cross_seed = int(table.get("cross_seed", 0) or 0)
    cross = _cross_aad(g1, g2, cross_seed) if g1 and g2 else ""
    return _CaseBind(
        rows=rows,
        cross=cross,
        g1=g1,
        g2=g2,
        cross_seed=cross_seed,
        case_spec=spec,
        footer_view=view,
        authority=table,
        projection=proj,
        blob=raw,
    )


def _decrypt_chunk(blob: bytes, aad: bytes, off: int, *, blob_only: bool = False) -> bytes:
    if blob_only:
        key = hashlib.sha256(blob).digest()
    else:
        key = hashlib.sha256(aad + struct.pack("<I", off & 0xFFFFFFFF)).digest()
    return bytes(b ^ key[i % 32] for i, b in enumerate(blob))


def _part_sig_for(case_id: str, *, blob_only: bool = False) -> str:
    doc = _bind_case(case_id)
    spec = doc.case_spec
    view = doc.footer_view
    table = doc.authority
    raw = doc.blob
    key_mat = _key_material(view["keys"])
    g = view["groups"][0]
    grp = g["grp"]
    key = _resolve_key(key_mat, grp, table)
    lane = _effective_lane(spec, doc.projection, grp)
    seed = _seed_bytes(g["seed"], table["aad_base"])
    aad = _rotate_aad(seed, grp, lane)
    part_aad = b"" if blob_only else (key + aad)
    ch = next(c for c in view["chunks"] if c["grp"] == grp)
    off = spec.get("part_off", ch["off"]) if case_id == "r2" else ch["off"]
    chunk = raw[ch["off"] : ch["off"] + ch["ln"]]
    plain = _decrypt_chunk(chunk, part_aad, off, blob_only=blob_only)
    return hashlib.sha256(plain).hexdigest()[:12]


def r2_part_sig(*, blob_only: bool = False) -> str:
    return _part_sig_for("r2", blob_only=blob_only)


def b2_part_sig() -> str:
    return _part_sig_for("b2")


def f7_part_sig() -> str:
    return _part_sig_for("f7")


def f7_cross_plain() -> str:
    doc = _bind_case("f7")
    return _cross_aad(doc.g1, doc.g2, 0)


def compute_a() -> dict:
    doc = _bind_case("k4")
    return {"case_id": "k4", "rows": doc.rows}


def compute_b() -> dict:
    doc = _bind_case("r2")
    return {
        "aad_hex": doc.rows[0]["aad_hex"],
        "row_hex": doc.rows[1]["row_hex"],
        "part_sig": r2_part_sig(),
    }


def compute_c() -> dict:
    doc = _bind_case("f7")
    return {"cross_aad_digest": doc.cross, "row_hex": doc.rows[1]["row_hex"]}


def compute_d() -> tuple[str, str]:
    return r2_part_sig(), r2_part_sig(blob_only=True)


def compute_e() -> dict:
    doc = _bind_case("h3")
    meta = {"run_meta": {"case_id": "h3", "phase": "verify", "seq": 0}, "bind_rows": doc.rows}
    if doc.cross:
        meta["cross_aad_digest"] = doc.cross
    meta["record_digest"] = record_digest(meta)
    return {"record_digest": meta["record_digest"], "row_hex": doc.rows[0]["row_hex"]}


def compute_f() -> dict:
    doc = _bind_case("j6")
    return {"key_idx": doc.rows[0]["key_idx"], "row_hex": doc.rows[0]["row_hex"]}


def compute_g() -> dict:
    doc = _bind_case("n3")
    return {"aad_hex": doc.rows[1]["aad_hex"], "cross_aad_digest": doc.cross}


def compute_h() -> dict:
    j6 = _bind_case("j6")
    cross = _cross_aad(j6.g1, j6.g2, j6.cross_seed) if j6.g1 and j6.g2 else ""
    return {"cross_aad_digest": cross, "row_hex": j6.rows[0]["row_hex"]}


def compute_i() -> dict:
    doc = _bind_case("z5")
    return {
        "key_idx": doc.rows[0]["key_idx"],
        "aad_hex": doc.rows[1]["aad_hex"],
        "cross_aad_digest": doc.cross,
    }


def compute_j() -> dict:
    doc = _bind_case("f7")
    return {"cross_aad_digest": doc.cross}


def compute_l() -> dict:
    doc = _bind_case("q7")
    return {
        "key_idx": doc.rows[0]["key_idx"],
        "aad_hex": doc.rows[0]["aad_hex"],
        "cross_aad_digest": doc.cross,
    }


def compute_m() -> dict:
    doc = _bind_case("f7")
    return {"key_idx": doc.rows[0]["key_idx"], "row_hex": doc.rows[0]["row_hex"]}


def compute_k() -> tuple[str, str]:
    doc = _bind_case("r2")
    meta = {
        "run_meta": {"case_id": "r2", "phase": "verify", "seq": 0},
        "bind_rows": doc.rows,
        "part_sig": r2_part_sig(),
    }
    if doc.cross:
        meta["cross_aad_digest"] = doc.cross
    digest = record_digest(meta)
    return digest, r2_part_sig()


def compute_n() -> dict:
    doc = _bind_case("w9")
    return {
        "key_idx": doc.rows[0]["key_idx"],
        "row_hex": doc.rows[0]["row_hex"],
        "aad_hex": doc.rows[1]["aad_hex"],
        "cross_aad_digest": doc.cross,
    }


def compute_o() -> dict:
    doc = _bind_case("b2")
    return {
        "aad_hex": doc.rows[0]["aad_hex"],
        "part_sig": b2_part_sig(),
    }


def compute_p() -> dict:
    doc = _bind_case("c8")
    return {
        "key_idx": doc.rows[0]["key_idx"],
        "aad_hex": doc.rows[1]["aad_hex"],
        "cross_aad_digest": doc.cross,
    }


def compute_r() -> dict:
    doc = _bind_case("d6")
    return {
        "key_idx": doc.rows[1]["key_idx"],
        "row_hex": doc.rows[1]["row_hex"],
        "aad_hex": doc.rows[1]["aad_hex"],
        "cross_aad_digest": doc.cross,
    }


def compute_s() -> dict:
    """Held-out n3 arm versus global ring tip decoy."""
    good = _bind_case("n3")
    tip = _project_epoch(99)
    decoy_lane = int(tip[1]["aad_epoch"]) if 1 in tip else 0
    wrong = _rotate_aad(
        _seed_bytes(good.footer_view["groups"][1]["seed"], good.authority["aad_base"]),
        good.footer_view["groups"][1]["grp"],
        decoy_lane,
    ).hex()
    return {
        "aad_hex": good.rows[1]["aad_hex"],
        "cross_aad_digest": good.cross,
        "row_hex": wrong,
    }

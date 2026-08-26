"""Verifier for shuffleboard wax-lane claim board — independent reference allotment."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
BIN = APP / "bin" / "waxlane-allot"
COURT = Path("/app/data/rink-lanes.json")
LOTS = Path("/app/data/disk-packages.json")
SLATE = Path("/app/state/chalk-slate.json")
EPOCH = Path("/app/state/chalk-epoch")
LEDGER = Path("/app/output/wax-lane-claim-ledger.json")
PROBE_COURT = Path("/opt/verifier-fixtures/court-probes/alt-court.json")
PROBE_LOTS = Path("/opt/verifier-fixtures/court-probes/alt-lots.json")


def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(BIN),
            *args,
        ],
        capture_output=True,
        text=True,
        check=check,
    )


def _reset_state() -> None:
    Path("/app/output").mkdir(parents=True, exist_ok=True)
    Path("/app/state").mkdir(parents=True, exist_ok=True)
    for p in (SLATE, EPOCH, LEDGER):
        if p.exists():
            p.unlink()


def _load_court(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_lots(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["lots"]


def _court_digest(court: dict) -> str:
    lanes = sorted(court["lanes"], key=lambda x: x["id"])
    out = {
        "court_id": court["court_id"],
        "lanes": [
            {
                "id": lane["id"],
                "band": lane["band"],
                "mutex_group": lane["mutex_group"],
            }
            for lane in lanes
        ],
    }
    raw = json.dumps(out, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _normalize_lots(lots: list[dict]) -> list[dict]:
    out = []
    for lot in sorted(lots, key=lambda x: x["id"]):
        out.append(
            {
                "id": lot["id"],
                "lanes": sorted(lot["lanes"]),
                "score": lot["score"],
                "weight": lot["weight"],
            }
        )
    return out


def _lots_digest(lots: list[dict]) -> str:
    norm = _normalize_lots(lots)
    raw = json.dumps(norm, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


def _lot_band_ok(lot: dict, lanes: dict[str, dict]) -> bool:
    ids = lot["lanes"]
    if not ids:
        return False
    bands = set()
    groups = set()
    for lid in ids:
        if lid not in lanes:
            return False
        bands.add(lanes[lid]["band"])
        g = lanes[lid]["mutex_group"]
        if g in groups:
            return False
        groups.add(g)
    return len(bands) == 1


def _compatible(subset: list[dict], lanes: dict[str, dict]) -> bool:
    used_lanes: set[str] = set()
    used_groups: set[str] = set()
    for lot in subset:
        for lid in lot["lanes"]:
            if lid in used_lanes:
                return False
            g = lanes[lid]["mutex_group"]
            if g in used_groups:
                return False
            used_lanes.add(lid)
            used_groups.add(g)
    return True


def _reference_solve(court: dict, lots: list[dict]) -> tuple[list[dict], dict[str, str]]:
    lanes = {lane["id"]: lane for lane in court["lanes"]}
    illegal: dict[str, str] = {}
    legal: list[dict] = []
    for lot in lots:
        if not _lot_band_ok(lot, lanes):
            illegal[lot["id"]] = "illegal_band"
        else:
            legal.append(lot)
    best_score = -1
    best_key = ""
    best_subset: list[dict] = []
    n = len(legal)
    for mask in range(1 << n):
        subset = [legal[i] for i in range(n) if mask & (1 << i)]
        if not _compatible(subset, lanes):
            continue
        score = sum(x["score"] for x in subset)
        key = ",".join(sorted(x["id"] for x in subset))
        if score > best_score or (score == best_score and (best_key == "" or key < best_key)):
            best_score = score
            best_key = key
            best_subset = subset
    accepted = sorted(best_subset, key=lambda x: x["id"])
    return accepted, illegal


def _fingerprint(court_id: str, accepted: list[dict]) -> str:
    ids = sorted(a["id"] for a in accepted)
    parts = [court_id, "|", ",".join(ids), "|"]
    by_id = {a["id"]: a for a in accepted}
    for lid in ids:
        lanes = sorted(by_id[lid]["lanes"])
        parts.append(f"{lid}:{','.join(lanes)};")
    return hashlib.sha256("".join(parts).encode()).hexdigest()


def _reject_reasons(
    court: dict,
    lots: list[dict],
    accepted: list[dict],
    illegal: dict[str, str],
) -> list[dict]:
    lanes = {lane["id"]: lane for lane in court["lanes"]}
    accepted_ids = {a["id"] for a in accepted}
    used_lanes: set[str] = set()
    used_groups: set[str] = set()
    for a in accepted:
        for lid in a["lanes"]:
            used_lanes.add(lid)
            used_groups.add(lanes[lid]["mutex_group"])
    rejected = []
    for lot in lots:
        if lot["id"] in accepted_ids:
            continue
        if lot["id"] in illegal:
            reason = illegal[lot["id"]]
        elif any(lid in used_lanes for lid in lot["lanes"]):
            reason = "collided"
        elif any(lanes.get(lid, {}).get("mutex_group") in used_groups for lid in lot["lanes"]):
            reason = "mutex"
        else:
            reason = "suboptimal"
        rejected.append({"lot_id": lot["id"], "reason": reason})
    return sorted(rejected, key=lambda x: x["lot_id"])


@pytest.fixture(autouse=True)
def _clean() -> None:
    _reset_state()
    yield
    _reset_state()


def test_t762de0_wlcb_binary_exists() -> None:
    """CLI binary must exist and be executable after rebuild."""
    assert BIN.is_file()
    assert os.access(BIN, os.X_OK)


def test_t762de0_wlcb_chalk_writes_slate_without_ledger() -> None:
    """chalk writes slate only and does not create the claim ledger."""
    _run(
        [
            "chalk",
            "--court",
            str(COURT),
            "--lots",
            str(LOTS),
            "--slate",
            str(SLATE),
            "--epoch",
            str(EPOCH),
        ]
    )
    assert SLATE.is_file()
    assert not LEDGER.exists()


def test_t762de0_wlcb_chalk_staging_snapshot_schema_and_digest() -> None:
    """chalk staging snapshot schema, court digest, and lots digest match the contract."""
    court = _load_court(COURT)
    lots = _load_lots(LOTS)
    _run(
        [
            "chalk",
            "--court",
            str(COURT),
            "--lots",
            str(LOTS),
            "--slate",
            str(SLATE),
            "--epoch",
            str(EPOCH),
        ]
    )
    slate = json.loads(SLATE.read_text(encoding="utf-8"))
    assert slate["schema"] == "wax-chalk-slate/v1"
    assert slate["court_id"] == court["court_id"]
    assert slate["court_digest"] == _court_digest(court)
    assert slate["lots_digest"] == _lots_digest(lots)
    assert slate["lots"] == _normalize_lots(lots)
    assert slate["chalk_epoch"] == 1


def test_t762de0_wlcb_epoch_increments_across_chalks() -> None:
    """second chalk advances chalk_epoch using the persisted epoch file."""
    args = [
        "chalk",
        "--court",
        str(COURT),
        "--lots",
        str(LOTS),
        "--slate",
        str(SLATE),
        "--epoch",
        str(EPOCH),
    ]
    _run(args)
    first = json.loads(SLATE.read_text(encoding="utf-8"))["chalk_epoch"]
    _run(args)
    second = json.loads(SLATE.read_text(encoding="utf-8"))["chalk_epoch"]
    assert first == 1
    assert second == 2
    assert EPOCH.read_text(encoding="utf-8").strip() == "3"


def test_t762de0_wlcb_allot_without_slate_fails() -> None:
    """allot refuses when chalk slate is missing."""
    proc = _run(
        ["allot", "--court", str(COURT), "--slate", str(SLATE), "--ledger", str(LEDGER)],
        check=False,
    )
    assert proc.returncode != 0
    assert not LEDGER.exists()


def test_t762de0_wlcb_allot_rejects_tampered_lots_digest() -> None:
    """allot refuses a slate whose lots_digest does not recompute."""
    _run(
        [
            "chalk",
            "--court",
            str(COURT),
            "--lots",
            str(LOTS),
            "--slate",
            str(SLATE),
            "--epoch",
            str(EPOCH),
        ]
    )
    slate = json.loads(SLATE.read_text(encoding="utf-8"))
    slate["lots_digest"] = "0" * 64
    SLATE.write_text(json.dumps(slate), encoding="utf-8")
    proc = _run(
        ["allot", "--court", str(COURT), "--slate", str(SLATE), "--ledger", str(LEDGER)],
        check=False,
    )
    assert proc.returncode != 0


def test_t762de0_wlcb_claim_export_writes_ledger_schema() -> None:
    """claim export writes ledger with required schema and court_id."""
    court = _load_court(COURT)
    _run(
        [
            "claim",
            "--court",
            str(COURT),
            "--lots",
            str(LOTS),
            "--slate",
            str(SLATE),
            "--epoch",
            str(EPOCH),
            "--ledger",
            str(LEDGER),
        ]
    )
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert led["schema"] == "wax-lane-claim-ledger/v1"
    assert led["court_id"] == court["court_id"]
    assert "accepted" in led and "rejected" in led
    assert "allot_fingerprint" in led


def test_t762de0_wlcb_bundled_accepted_matches_reference() -> None:
    """bundled fixtures accept the welfare-max lex-least set from the reference solver."""
    court = _load_court(COURT)
    lots = _load_lots(LOTS)
    accepted, _ = _reference_solve(court, lots)
    _run(
        [
            "claim",
            "--court",
            str(COURT),
            "--lots",
            str(LOTS),
            "--slate",
            str(SLATE),
            "--epoch",
            str(EPOCH),
            "--ledger",
            str(LEDGER),
        ]
    )
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    got = [row["lot_id"] for row in led["accepted"]]
    assert got == [a["id"] for a in accepted]
    assert led["total_score"] == sum(a["score"] for a in accepted)


def test_t762de0_wlcb_bundled_fingerprint_matches_reference() -> None:
    """allot_fingerprint matches independent SHA-256 fingerprint math."""
    court = _load_court(COURT)
    lots = _load_lots(LOTS)
    accepted, _ = _reference_solve(court, lots)
    _run(
        [
            "claim",
            "--court",
            str(COURT),
            "--lots",
            str(LOTS),
            "--slate",
            str(SLATE),
            "--epoch",
            str(EPOCH),
            "--ledger",
            str(LEDGER),
        ]
    )
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert led["allot_fingerprint"] == _fingerprint(court["court_id"], accepted)


def test_t762de0_wlcb_rejected_reasons_match_reference() -> None:
    """rejected lot reasons follow illegal_band then collided then mutex then suboptimal."""
    court = _load_court(COURT)
    lots = _load_lots(LOTS)
    accepted, illegal = _reference_solve(court, lots)
    expect = _reject_reasons(court, lots, accepted, illegal)
    _run(
        [
            "claim",
            "--court",
            str(COURT),
            "--lots",
            str(LOTS),
            "--slate",
            str(SLATE),
            "--epoch",
            str(EPOCH),
            "--ledger",
            str(LEDGER),
        ]
    )
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert led["rejected"] == expect


def test_t762de0_wlcb_illegal_mixed_band_lots_rejected() -> None:
    """mixed-band packages appear as illegal_band in rejected."""
    _run(
        [
            "claim",
            "--court",
            str(COURT),
            "--lots",
            str(LOTS),
            "--slate",
            str(SLATE),
            "--epoch",
            str(EPOCH),
            "--ledger",
            str(LEDGER),
        ]
    )
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    by_id = {r["lot_id"]: r["reason"] for r in led["rejected"]}
    assert by_id.get("W-b") == "illegal_band"
    assert by_id.get("W-f") == "illegal_band"


def test_t762de0_wlcb_accepted_lanes_sorted_and_banded() -> None:
    """accepted rows expose sorted lanes and a single friction band."""
    court = _load_court(COURT)
    lanes = {lane["id"]: lane for lane in court["lanes"]}
    _run(
        [
            "claim",
            "--court",
            str(COURT),
            "--lots",
            str(LOTS),
            "--slate",
            str(SLATE),
            "--epoch",
            str(EPOCH),
            "--ledger",
            str(LEDGER),
        ]
    )
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    for row in led["accepted"]:
        assert row["lanes"] == sorted(row["lanes"])
        bands = {lanes[x]["band"] for x in row["lanes"]}
        assert bands == {row["band"]}


def test_t762de0_wlcb_mutex_groups_exclusive_across_accepted() -> None:
    """accepted allotment never claims two lanes from the same mutex group."""
    court = _load_court(COURT)
    lanes = {lane["id"]: lane for lane in court["lanes"]}
    _run(
        [
            "claim",
            "--court",
            str(COURT),
            "--lots",
            str(LOTS),
            "--slate",
            str(SLATE),
            "--epoch",
            str(EPOCH),
            "--ledger",
            str(LEDGER),
        ]
    )
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    groups = []
    for row in led["accepted"]:
        for lid in row["lanes"]:
            groups.append(lanes[lid]["mutex_group"])
    assert len(groups) == len(set(groups))


def test_t762de0_wlcb_ledger_binds_slate_digest_and_epoch() -> None:
    """ledger copies lots_digest and chalk_epoch from the chalk slate."""
    _run(
        [
            "claim",
            "--court",
            str(COURT),
            "--lots",
            str(LOTS),
            "--slate",
            str(SLATE),
            "--epoch",
            str(EPOCH),
            "--ledger",
            str(LEDGER),
        ]
    )
    slate = json.loads(SLATE.read_text(encoding="utf-8"))
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert led["lots_digest"] == slate["lots_digest"]
    assert led["chalk_epoch"] == slate["chalk_epoch"]


def test_t762de0_wlcb_export_uses_ingest_staging_not_live_lots_file() -> None:
    """export allot ignores poisoned lots and uses ingest chalk staging snapshot lots."""
    _run(
        [
            "chalk",
            "--court",
            str(COURT),
            "--lots",
            str(LOTS),
            "--slate",
            str(SLATE),
            "--epoch",
            str(EPOCH),
        ]
    )
    poisoned = {"lots": [{"id": "POISON", "lanes": ["L1"], "score": 99, "weight": 1}]}
    backup = LOTS.read_text(encoding="utf-8")
    try:
        LOTS.write_text(json.dumps(poisoned), encoding="utf-8")
        _run(["allot", "--court", str(COURT), "--slate", str(SLATE), "--ledger", str(LEDGER)])
        led = json.loads(LEDGER.read_text(encoding="utf-8"))
        ids = [r["lot_id"] for r in led["accepted"]]
        assert "POISON" not in ids
        assert "POISON" not in [r["lot_id"] for r in led["rejected"]]
    finally:
        LOTS.write_text(backup, encoding="utf-8")


def test_t762de0_wlcb_buff_catalog_is_decoy_ok() -> None:
    """buff-catalog prints decorative catalog lines without writing ledger."""
    proc = _run(["buff-catalog", "--catalog", "/app/data/spray-catalog.json"])
    assert proc.returncode == 0
    assert "B-glow" in proc.stdout
    assert not LEDGER.exists()


def test_t762de0_wlcb_hidden_probe_allotment_matches_reference() -> None:
    """hidden court probe accepts reference optimum distinct from bundled fixtures."""
    # /opt/verifier-fixtures/court-probes trap path
    work = Path("/tmp/wax-probe")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    slate = work / "slate.json"
    epoch = work / "epoch"
    ledger = work / "ledger.json"
    court = _load_court(PROBE_COURT)
    lots = _load_lots(PROBE_LOTS)
    accepted, illegal = _reference_solve(court, lots)
    _run(
        [
            "claim",
            "--court",
            str(PROBE_COURT),
            "--lots",
            str(PROBE_LOTS),
            "--slate",
            str(slate),
            "--epoch",
            str(epoch),
            "--ledger",
            str(ledger),
        ]
    )
    led = json.loads(ledger.read_text(encoding="utf-8"))
    assert [r["lot_id"] for r in led["accepted"]] == [a["id"] for a in accepted]
    assert led["total_score"] == sum(a["score"] for a in accepted)
    assert led["allot_fingerprint"] == _fingerprint(court["court_id"], accepted)
    assert led["rejected"] == _reject_reasons(court, lots, accepted, illegal)


def test_t762de0_wlcb_hidden_probe_mutex_and_band_trap() -> None:
    """hidden probe rejects mixed-band illegal packages present only in probe fixtures."""
    # /opt/verifier-fixtures/court-probes mutex trap
    work = Path("/tmp/wax-probe2")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    ledger = work / "ledger.json"
    _run(
        [
            "claim",
            "--court",
            str(PROBE_COURT),
            "--lots",
            str(PROBE_LOTS),
            "--slate",
            str(work / "slate.json"),
            "--epoch",
            str(work / "epoch"),
            "--ledger",
            str(ledger),
        ]
    )
    led = json.loads(ledger.read_text(encoding="utf-8"))
    by_id = {r["lot_id"]: r["reason"] for r in led["rejected"]}
    assert by_id.get("H-five") == "illegal_band"
    assert by_id.get("H-six") == "illegal_band"


def test_t762de0_wlcb_claim_idempotent_score_stable() -> None:
    """two claim runs with reset epoch produce the same total_score and fingerprint."""
    def once() -> dict:
        _reset_state()
        _run(
            [
                "claim",
                "--court",
                str(COURT),
                "--lots",
                str(LOTS),
                "--slate",
                str(SLATE),
                "--epoch",
                str(EPOCH),
                "--ledger",
                str(LEDGER),
            ]
        )
        return json.loads(LEDGER.read_text(encoding="utf-8"))

    a = once()
    b = once()
    assert a["total_score"] == b["total_score"]
    assert a["allot_fingerprint"] == b["allot_fingerprint"]
    assert [r["lot_id"] for r in a["accepted"]] == [r["lot_id"] for r in b["accepted"]]


def test_t762de0_wlcb_accepted_sorted_by_lot_id() -> None:
    """accepted array is sorted by lot_id ascending."""
    _run(
        [
            "claim",
            "--court",
            str(COURT),
            "--lots",
            str(LOTS),
            "--slate",
            str(SLATE),
            "--epoch",
            str(EPOCH),
            "--ledger",
            str(LEDGER),
        ]
    )
    led = json.loads(LEDGER.read_text(encoding="utf-8"))
    ids = [r["lot_id"] for r in led["accepted"]]
    assert ids == sorted(ids)


def test_t762de0_wlcb_sample_fixtures_present() -> None:
    """bundled rink lanes and disk packages fixtures exist for playtest loads."""
    assert COURT.is_file()
    assert LOTS.is_file()
    assert "/app/data/rink-lanes.json" == str(COURT)
    assert "/app/data/disk-packages.json" == str(LOTS)

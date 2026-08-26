"""Conformal coverage witness verification for offline Go workspace carry slot convergence."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
ENV = APP / "environment"
OUT = APP / "output" / "cp_witness.json"
ANCHOR = Path(__file__).resolve().parent / "anchor"
BUILD = "/app/environment/scripts/rebuild_bins.sh"
DRIVE = "/app/environment/scripts/drive_matrix.sh"
CP_RUN = "/app/bin/cp_run"
CP_AUDIT = "/app/bin/cp_audit"
MIG = "/app/environment/migrations/cln8.sh"
CARRY_SEED = "/app/environment/fixtures/seed/cp_seed.bin"
PROFILES = ["lane_amber", "lane_birch", "lane_coral", "lane_drift"]
SCHEDULE_FILES = {"lane_amber": "xa", "lane_birch": "xb", "lane_coral": "xc", "lane_drift": "xd"}
MODES = ["fresh_score", "rotate_split", "trim_holdout", "mirror_restore"]
EXPECTED_ROWS_TOTAL = 96

# (environment relative path, tests/anchor relative path)
ANCHOR_PAIRS = [
    ("c44.txt", "ledger_auth.txt"),
    ("p3/schedules/xa.json", "p3/schedules/xa.json"),
    ("p3/schedules/xb.json", "p3/schedules/xb.json"),
    ("p3/schedules/xc.json", "p3/schedules/xc.json"),
    ("p3/schedules/xd.json", "p3/schedules/xd.json"),
    ("m4/mirrors/m_a.json", "m4/mirrors/m_a.json"),
    ("m4/mirrors/m_b.json", "m4/mirrors/m_b.json"),
    ("m4/mirrors/m_c.json", "m4/mirrors/m_c.json"),
    ("fixtures/b5/f4.bin", "fixtures/b5/f4.bin"),
    ("fixtures/b5/f5.bin", "fixtures/b5/f5.bin"),
]


def _cp_file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cp_trunc16(parts: list[str | bytes]) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode() if isinstance(part, str) else part)
    return digest.hexdigest()[:16]


def _cp_score_hex(issuer: str, this_up: str, serials: list[str]) -> str:
    serials_sorted = ",".join(sorted(serials))
    return _cp_trunc16([f"{issuer}|{this_up}|{serials_sorted}"])


def _cp_cover_hex(profile_pfx: str, blob: bytes) -> str:
    return _cp_trunc16([profile_pfx.encode(), blob])


def _cp_lag_code(a: str, b: str) -> int:
    ai = bytes.fromhex(a[:16].ljust(16, "0")[:16])
    bi = bytes.fromhex(b[:16].ljust(16, "0")[:16])
    return sum(abs(x - y) for x, y in zip(ai, bi))


def _cp_band_hex(stamps: list[str]) -> str:
    return _cp_trunc16(["".join(sorted(stamps))])[:12]


def _cp_tagged_stamp(stamp: str, mode: str) -> str:
    if mode == "fresh_score":
        return stamp
    return stamp + ":" + mode


def _cp_witness_digest(cycles: list[dict]) -> str:
    tuples = sorted(
        [(c["profile_id"], c["pass_mode"], c["band_hex"], c["carry_span"]) for c in cycles],
        key=lambda t: (t[0], t[1]),
    )
    parts = [f"{t}:{m}:{d}:{s}" for t, m, d, s in tuples]
    return _cp_trunc16(["|".join(parts)])


def _cp_resolve_this_up(local: str, remote: str, retract: bool) -> str:
    if retract:
        return local
    return local if local > remote else remote


def _cp_slot_key(path: str, ver: str, epoch_dn: str, stamp: str) -> str:
    return "|".join([path, ver, epoch_dn, stamp])


def _cp_anchor_text(rel: str) -> str:
    return (ANCHOR / rel).read_text(encoding="utf-8")


def _cp_anchor_json(rel: str) -> dict:
    return json.loads(_cp_anchor_text(rel))


def _cp_anchor_bytes(rel: str) -> bytes:
    return (ANCHOR / rel).read_bytes()


def _ledger_rows_from_anchor() -> list[dict]:
    rows: list[dict] = []
    for line in _cp_anchor_text("ledger_auth.txt").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts[0] == "tomb":
            rows.append({"path": "", "version": parts[1], "tomb": True, "this_up": "tomb"})
            continue
        path, ver = parts[0], parts[1]
        this_up = parts[2] if len(parts) >= 3 else ver
        rows.append({"path": path, "version": ver, "tomb": False, "this_up": this_up})
    return rows


def _ledger_lookup(rows: list[dict], path: str, ver: str) -> dict:
    for row in rows:
        if row["path"] == path and row["version"] == ver:
            return row
    return {"path": path, "version": ver, "tomb": False, "this_up": "v0"}


def _expect_cycle_pass(sch: dict, mode: str, sums: list[dict], cache: dict[str, int]) -> dict:
    cache_before = len(cache)
    stamps: dict[str, str] = {}
    rows: list[dict] = []
    for mod in sch["modules"]:
        srow = _ledger_lookup(sums, mod["path"], mod["version"])
        shard = _cp_anchor_json(f"m4/mirrors/{mod['shard_ref']}.json")
        retract = bool(srow["tomb"] or mod.get("tomb"))
        this_up = _cp_resolve_this_up(srow["this_up"], shard["this_up"], retract)
        slot = _cp_slot_key(
            mod["path"],
            mod["version"],
            sch["epoch_dn"],
            _cp_tagged_stamp(sch["epoch_stamp"], mode),
        )
        if slot not in cache:
            cache[slot] = len(cache) + 1
        blob = _cp_anchor_bytes(f"fixtures/b5/{mod['frame']}.bin")
        cover = _cp_cover_hex(sch["profile_pfx"], blob)
        stamp = _cp_score_hex(shard["issuer"], this_up, shard["serials"])
        stamps[mod["role"]] = stamp
        skew = lag = 0
        echo = mod.get("echo_role") or ""
        if echo and echo in stamps:
            skew = _cp_lag_code(stamp, stamps[echo])
            lag = _cp_lag_code(stamp, stamps[echo])
        rows.append(
            {
                "role": mod["role"],
                "score_hex": stamp,
                "cover_hex": cover,
                "nc_skew": skew,
                "lag_code": lag,
                "slot_id": slot,
            }
        )
    stamp_list = [row["score_hex"] for row in rows]
    frame_unit = sch.get("frame_unit", 64)
    grant_unit = sch.get("grant_unit", 32)
    used = (len(cache) - cache_before) * frame_unit + len(rows) * grant_unit
    span = sch["cap_bytes"] - used
    return {
        "profile_id": sch["profile_id"],
        "pass_mode": mode,
        "band_hex": _cp_band_hex(stamp_list),
        "carry_span": span,
        "budget_used": used,
        "rows": rows,
    }


def _cp_expect_witness() -> dict:
    sums = _ledger_rows_from_anchor()
    cache: dict[str, int] = {}
    cycles: list[dict] = []
    row_total = 0
    for tenant in PROFILES:
        sch = _cp_anchor_json(f"p3/schedules/{SCHEDULE_FILES[tenant]}.json")
        for mode in MODES:
            cycle = _expect_cycle_pass(sch, mode, sums, cache)
            cycles.append(cycle)
            row_total += len(cycle["rows"])
    status = "settled"
    sum_span = 0
    for cycle in cycles:
        if cycle["carry_span"] != 0:
            sum_span = cycle["carry_span"]
            status = "unsettled"
        for row in cycle["rows"]:
            if row["nc_skew"] != 0:
                status = "unsettled"
    return {
        "cycles": cycles,
        "summary": {
            "rows_total": row_total,
            "matrix_status": status,
            "carry_span": sum_span,
            "witness_digest": _cp_witness_digest(cycles),
        },
    }


def _cp_run_build() -> None:
    proc = subprocess.run(["bash", BUILD], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise AssertionError(
            f"command failed: bash {BUILD}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )


def _cp_run_drive() -> None:
    proc = subprocess.run(["bash", DRIVE], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise AssertionError(
            f"command failed: bash {DRIVE}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )


def _run_cp_run() -> None:
    proc = subprocess.run(
        [CP_RUN, "--out", "/app/output/cp_witness.json"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"command failed: {CP_RUN} --out /app/output/cp_witness.json\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )


def _run_migration() -> None:
    proc = subprocess.run(
        ["bash", MIG, "--apply", CARRY_SEED],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"command failed: bash {MIG} --apply {CARRY_SEED}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )


def _cp_check_anchors() -> None:
    for env_rel, anchor_rel in ANCHOR_PAIRS:
        env_path = ENV / env_rel
        anchor_path = ANCHOR / anchor_rel
        assert env_path.exists(), f"missing workspace file: {env_rel}"
        assert _cp_file_digest(env_path) == _cp_file_digest(anchor_path), f"workspace tampered: {env_rel}"


def _cp_rebuild_bins() -> None:
    _cp_run_build()


def _cp_drive_witness() -> dict:
    if OUT.exists():
        OUT.unlink()
    _cp_run_drive()
    return json.loads(OUT.read_text(encoding="utf-8"))


def _cp_graded_witness() -> dict:
    _cp_check_anchors()
    _cp_rebuild_bins()
    return _cp_drive_witness()


def _cp_pick_cycle(doc: dict, tenant: str, mode: str) -> dict:
    for cycle in doc["cycles"]:
        if cycle["profile_id"] == tenant and cycle["pass_mode"] == mode:
            return cycle
    raise KeyError((tenant, mode))


@pytest.fixture(scope="module")
def expect() -> dict:
    return _cp_expect_witness()


@pytest.fixture(scope="module")
def graded() -> dict:
    if OUT.exists():
        try:
            cached = json.loads(OUT.read_text(encoding="utf-8"))
            if cached.get("summary", {}).get("matrix_status") == "settled":
                return cached
        except (json.JSONDecodeError, OSError):
            pass
    return _cp_graded_witness()


def test_cp_case_01(graded: dict) -> None:
    """Witness schema has sixteen settled cycles."""
    assert len(graded["cycles"]) == 16
    assert graded["summary"]["matrix_status"] == "settled"
    assert "cycles" in graded and "summary" in graded
    assert graded["summary"].get("matrix_status") == "settled"
    assert isinstance(graded["cycles"], list)


def test_cp_case_02(graded: dict, expect: dict) -> None:
    """Witness digest matches anchored reference."""
    assert graded["summary"]["witness_digest"] == expect["summary"]["witness_digest"]
    assert len(graded["summary"]["witness_digest"]) == 16

    assert isinstance(graded["summary"]["witness_digest"], str)
    assert graded["summary"]["witness_digest"] != ""
    assert all("profile_id" in c for c in graded["cycles"])
    assert all("pass_mode" in c for c in graded["cycles"])
    assert all("band_hex" in c for c in graded["cycles"])
    assert all(isinstance(c["carry_span"], int) for c in graded["cycles"])



def test_cp_case_03(graded: dict) -> None:
    """Drive emits at least sixteen trace files."""
    traces = list((APP / "output" / "mode_traces").glob("*.json"))
    assert len(traces) >= 16


def test_cp_case_04(graded: dict, expect: dict) -> None:
    """Each tenant fresh_score band_hex matches anchored reference."""
    for tenant in PROFILES:
        assert _cp_pick_cycle(graded, tenant, "fresh_score")["band_hex"] == _cp_pick_cycle(expect, tenant, "fresh_score")["band_hex"]


def test_cp_case_05(graded: dict) -> None:
    """rotate_split passes keep carry_span zero."""
    for tenant in PROFILES:
        assert _cp_pick_cycle(graded, tenant, "rotate_split")["carry_span"] == 0


def test_cp_case_06(graded: dict) -> None:
    """Vault rows present on every mode."""
    for mode in MODES:
        assert len(_cp_pick_cycle(graded, "lane_amber", mode)["rows"]) == 6


def test_cp_case_07(graded: dict, expect: dict) -> None:
    """Lane profile slot_id differs from lane_amber under rotation."""
    lane_amber_slot = _cp_pick_cycle(graded, "lane_amber", "fresh_score")["rows"][0]["slot_id"]
    lane_slot = _cp_pick_cycle(graded, "lane_coral", "fresh_score")["rows"][0]["slot_id"]
    assert lane_amber_slot != lane_slot
    assert lane_slot == _cp_pick_cycle(expect, "lane_coral", "fresh_score")["rows"][0]["slot_id"]


def test_cp_case_08(graded: dict) -> None:
    """Rollback tail mode converges for lane_drift."""
    cycle = _cp_pick_cycle(graded, "lane_drift", "trim_holdout")
    assert cycle["carry_span"] == 0
    assert cycle["pass_mode"] == "trim_holdout"


def test_cp_case_09(graded: dict, expect: dict) -> None:
    """Mirror replay cover_hex matches anchored frames."""
    got = _cp_pick_cycle(graded, "lane_birch", "mirror_restore")
    exp = _cp_pick_cycle(expect, "lane_birch", "mirror_restore")
    assert got["rows"][0]["cover_hex"] == exp["rows"][0]["cover_hex"]


def test_cp_case_10(graded: dict) -> None:
    """Echo pairs keep lag_code zero on lane_amber cold start."""
    rows = {r["role"]: r for r in _cp_pick_cycle(graded, "lane_amber", "fresh_score")["rows"]}
    for primary, echo in [("lease", "lease_echo"), ("worker", "worker_echo"), ("bind", "bind_echo")]:
        assert rows[primary]["lag_code"] == 0
        assert rows[echo]["lag_code"] == 0


def test_cp_case_11(graded: dict) -> None:
    """Stub health preview differs from graded lane row."""
    stub = json.loads((ENV / "fixtures" / "q8" / "stub_health.json").read_text(encoding="utf-8"))
    graded_row = _cp_pick_cycle(graded, "lane_amber", "fresh_score")["rows"][0]["score_hex"]
    assert stub["interim_rows"][0]["score_hex"] != graded_row


def test_cp_case_12(graded: dict, expect: dict) -> None:
    """Tomb precedence score_hex matches anchored ledger authority."""
    row = next(r for r in _cp_pick_cycle(graded, "lane_amber", "fresh_score")["rows"] if r["role"] == "lease")
    exp = next(r for r in _cp_pick_cycle(expect, "lane_amber", "fresh_score")["rows"] if r["role"] == "lease")
    assert row["score_hex"] == exp["score_hex"]


def test_cp_case_13(graded: dict) -> None:
    """Every row nc_skew is zero when converged."""
    for tenant in PROFILES:
        for mode in MODES:
            for row in _cp_pick_cycle(graded, tenant, mode)["rows"]:
                assert row["nc_skew"] == 0


def test_cp_case_14(graded: dict) -> None:
    """Slot_id embeds schedule epoch_dn."""
    slot = _cp_pick_cycle(graded, "lane_amber", "rotate_split")["rows"][0]["slot_id"]
    sch = json.loads((ENV / "p3/schedules/xa.json").read_text(encoding="utf-8"))
    assert sch["epoch_dn"] in slot


def test_cp_case_15(graded: dict) -> None:
    """Mode tagging changes slot_id across cold and rotate_split."""
    cold = _cp_pick_cycle(graded, "lane_amber", "fresh_score")["rows"][0]["slot_id"]
    stop = _cp_pick_cycle(graded, "lane_amber", "rotate_split")["rows"][0]["slot_id"]
    assert cold != stop


def test_cp_case_16(graded: dict, expect: dict) -> None:
    """cover_hex matches anchored profile prefix and frame bytes."""
    for tenant, mode in [
        ("lane_amber", "trim_holdout"),
        ("lane_birch", "mirror_restore"),
        ("lane_coral", "rotate_split"),
        ("lane_drift", "fresh_score"),
    ]:
        got = _cp_pick_cycle(graded, tenant, mode)
        exp = _cp_pick_cycle(expect, tenant, mode)
        for grow, erow in zip(got["rows"], exp["rows"]):
            assert grow["cover_hex"] == erow["cover_hex"]


def test_cp_case_17(graded: dict) -> None:
    """Repeated drive yields identical band_hex."""
    first = _cp_pick_cycle(graded, "lane_birch", "fresh_score")["band_hex"]
    second = _cp_drive_witness()
    assert _cp_pick_cycle(second, "lane_birch", "fresh_score")["band_hex"] == first


def test_cp_case_18(graded: dict, expect: dict) -> None:
    """Rows total matches anchored schedule expansion."""
    assert graded["summary"]["rows_total"] == EXPECTED_ROWS_TOTAL
    assert graded["summary"]["rows_total"] == expect["summary"]["rows_total"]
    assert graded["summary"]["rows_total"] == 96
    assert expect["summary"]["rows_total"] == 96


def test_cp_case_19(graded: dict) -> None:
    """Summary carry_span is zero when converged."""
    assert graded["summary"]["carry_span"] == 0


def test_cp_case_20(graded: dict) -> None:
    """cp_audit full cycle audit exits zero on regenerated witness."""
    proc = subprocess.run(
        [CP_AUDIT, "--coverage-audit", "--out", "/app/output/cp_witness.json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0


def test_cp_case_21() -> None:
    """Contract docs exist for solver discovery."""
    assert (ENV / "docs" / "cp_contract.md").exists()
    assert (ENV / "docs" / "p3_notes.md").exists()


def test_cp_case_22() -> None:
    """Partial log tail remains available as partial evidence."""
    assert (ENV / "fixtures" / "logs" / "gt_tail.txt").read_text(encoding="utf-8")


def test_cp_case_23(graded: dict) -> None:
    """cover_hex values are sixteen lowercase hex digits."""
    row = _cp_pick_cycle(graded, "lane_amber", "fresh_score")["rows"][0]
    assert len(row["cover_hex"]) == 16


def test_cp_case_24(graded: dict, expect: dict) -> None:
    """Mux band_hex matches anchored reference on every mode."""
    for mode in MODES:
        assert _cp_pick_cycle(graded, "lane_drift", mode)["band_hex"] == _cp_pick_cycle(expect, "lane_drift", mode)["band_hex"]


def test_cp_case_25(graded: dict, expect: dict) -> None:
    """Lane worker row score_hex matches anchored shard issuer material."""
    got = next(r for r in _cp_pick_cycle(graded, "lane_coral", "mirror_restore")["rows"] if r["role"] == "worker")
    exp = next(r for r in _cp_pick_cycle(expect, "lane_coral", "mirror_restore")["rows"] if r["role"] == "worker")
    assert got["score_hex"] == exp["score_hex"]


def test_cp_case_26(graded: dict, expect: dict) -> None:
    """Lane bind cover_hex matches anchored fold material."""
    got = next(r for r in _cp_pick_cycle(graded, "lane_coral", "rotate_split")["rows"] if r["role"] == "bind")
    exp = next(r for r in _cp_pick_cycle(expect, "lane_coral", "rotate_split")["rows"] if r["role"] == "bind")
    assert got["cover_hex"] == exp["cover_hex"]


def test_cp_case_27(graded: dict, expect: dict) -> None:
    """Budget_used stays within anchored carry budgets."""
    for tenant in PROFILES:
        budget = json.loads((ENV / "p3/schedules" / f"{SCHEDULE_FILES[tenant]}.json").read_text(encoding="utf-8"))["cap_bytes"]
        for mode in MODES:
            assert _cp_pick_cycle(graded, tenant, mode)["budget_used"] <= budget


def test_cp_case_28() -> None:
    """Carry seed fixture exists for migration recovery."""
    seed = Path(CARRY_SEED)
    assert seed.exists() and seed.read_bytes()


def test_cp_case_29() -> None:
    """Workspace inputs match verifier anchor checksums."""
    _cp_check_anchors()


def test_cp_case_30(graded: dict) -> None:
    """Each tenant exposes all four pass_mode values."""
    for tenant in PROFILES:
        modes = [cycle["pass_mode"] for cycle in graded["cycles"] if cycle["profile_id"] == tenant]
        assert sorted(modes) == sorted(MODES)


def test_cp_case_31() -> None:
    """cp_run binary emission matches drive_matrix script output."""
    _cp_check_anchors()
    via_script = _cp_drive_witness()
    if OUT.exists():
        OUT.unlink()
    _run_cp_run()
    direct = json.loads(OUT.read_text(encoding="utf-8"))
    assert direct["summary"]["witness_digest"] == via_script["summary"]["witness_digest"]
    assert direct["cycles"] == via_script["cycles"]


def test_cp_case_32() -> None:
    """Hand-written witness JSON is replaced by a rebuild-and-drive pass."""
    _cp_check_anchors()
    bogus_digest = "dead" + "beef" * 2
    OUT.write_text(
        json.dumps(
            {
                "cycles": [],
                "summary": {
                    "witness_digest": bogus_digest,
                    "matrix_status": "settled",
                    "carry_span": 0,
                    "rows_total": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    witness = _cp_drive_witness()
    expect = _cp_expect_witness()
    assert witness["summary"]["witness_digest"] == expect["summary"]["witness_digest"]
    assert witness["summary"]["rows_total"] == EXPECTED_ROWS_TOTAL


def test_cp_case_33() -> None:
    """Recovery migration twice still yields converged witness."""
    _cp_check_anchors()
    _run_migration()
    _run_migration()
    witness = _cp_drive_witness()
    assert witness["summary"]["matrix_status"] == "settled"
    assert witness["summary"]["witness_digest"] == _cp_expect_witness()["summary"]["witness_digest"]

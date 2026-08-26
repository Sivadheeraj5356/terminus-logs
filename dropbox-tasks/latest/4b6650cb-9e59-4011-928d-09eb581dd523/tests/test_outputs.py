"""Verifier for volsweep rebuild, merge, and probe workflows."""

import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest

APP_ENV = Path("/app/environment")
VOLSWEEP_BIN = "/app/environment/target/release/volsweep"
LEDGER = Path("/app/output/sweep_ledger.json")
STATE = Path("/app/state/scope_state.json")
PROBE = Path("/app/output/probe_snapshot.json")

BASIS = 0xB0017000CAFEBABE
MULT = 137
MASK64 = (1 << 64) - 1
PRESERVE = 0x80000000


def _roll(buf: bytes) -> int:
    h = BASIS
    for b in buf:
        h = (h * MULT + b) & MASK64
    return h ^ len(buf)


def _load_manifest(profile: str) -> dict:
    return json.loads((APP_ENV / "ops/manifests" / f"{profile}.json").read_text())


def _load_overlay(profile: str) -> dict:
    return json.loads((APP_ENV / "ops/overlays" / f"{profile}.json").read_text())


def _effective_mask(profile: str, manifest: dict) -> int:
    overlay = _load_overlay(profile)
    return int(manifest["sweep_mask"]) & int(overlay["mask"])


def _load_cache() -> list[dict]:
    return json.loads((APP_ENV / "ops/sweep.cache").read_text())


def _resolve_width(profile: str, manifest: dict) -> int:
    for row in _load_cache():
        if row["profile"] == profile and row["manifest_gen"] >= manifest["manifest_gen"]:
            return int(row["width_ms"])
    return int(manifest["window_width_ms"])


def _u32_le(data: bytes, off: int) -> int:
    return int.from_bytes(data[off : off + 4], "little")


def _i32_le(data: bytes, off: int) -> int:
    return int.from_bytes(data[off : off + 4], "little", signed=True)


def _u64_le(data: bytes, off: int) -> int:
    return int.from_bytes(data[off : off + 8], "little")


def _u16_le(data: bytes, off: int) -> int:
    return int.from_bytes(data[off : off + 2], "little")


def _parse_journal(path: Path) -> tuple[dict, list[dict]]:
    data = path.read_bytes()
    header = {
        "rotate_gen": _u32_le(data, 4),
        "bound_rotate": _u32_le(data, 8),
        "slack": _u32_le(data, 12),
        "record_count": _u32_le(data, 16),
    }
    off = 32
    records: list[dict] = []
    for _ in range(header["record_count"]):
        scope_id = _u32_le(data, off)
        action_mask = _u32_le(data, off + 4)
        size_delta = _i32_le(data, off + 8)
        seq_num = _u32_le(data, off + 12)
        ts_ms = _u64_le(data, off + 16)
        path_len = _u16_le(data, off + 24)
        off += 26
        rel_path = data[off : off + path_len].decode()
        off += path_len
        payload_len = _u32_le(data, off)
        off += 4
        payload = data[off : off + payload_len]
        off += payload_len
        records.append(
            {
                "scope_id": scope_id,
                "action_mask": action_mask,
                "size_delta": size_delta,
                "seq_num": seq_num,
                "ts_ms": ts_ms,
                "rel_path": rel_path,
                "payload": payload,
            }
        )
    return header, records


def _journal_included(rotate_gen: int, bound: int, slack: int) -> bool:
    return rotate_gen <= bound + slack


def _mask_ok(record_mask: int, effective_mask: int) -> bool:
    stripped = record_mask & ~PRESERVE
    return (stripped & effective_mask) != 0


def _bucket_start(ts_ms: int, width: int) -> int:
    w = max(width, 1)
    return (ts_ms // w) * w


def _within_bucket_gap(recs: list[dict]) -> int:
    ordered = sorted(recs, key=lambda r: r["ts_ms"])
    total = 0
    for i in range(1, len(ordered)):
        gap = ordered[i]["seq_num"] - ordered[i - 1]["seq_num"] - 1
        if gap > 0:
            total += gap
    return total


def _rollup(records: list[dict], width: int) -> list[dict]:
    buckets: dict[int, list[dict]] = {}
    for rec in records:
        start = _bucket_start(rec["ts_ms"], width)
        buckets.setdefault(start, []).append(rec)
    rows = []
    prev_last_seq: int | None = None
    for start in sorted(buckets):
        recs = buckets[start]
        ordered = sorted(recs, key=lambda r: r["ts_ms"])
        deltas = [r["size_delta"] for r in ordered]
        gap_sum = _within_bucket_gap(ordered)
        if prev_last_seq is not None and ordered:
            cross = ordered[0]["seq_num"] - prev_last_seq - 1
            if cross > 0:
                gap_sum += cross
        prev_last_seq = ordered[-1]["seq_num"]
        rows.append(
            {
                "start_ms": start,
                "count": len(recs),
                "size_delta_sum": sum(deltas),
                "size_min": min(deltas),
                "size_max": max(deltas),
                "seq_gap_sum": gap_sum,
            }
        )
    return rows


def _collect_rebuild(profile: str) -> tuple[list[dict], int, dict]:
    manifest = _load_manifest(profile)
    effective = _effective_mask(profile, manifest)
    journal = APP_ENV / "fixtures" / profile / f"{profile.replace('site-', '')}.vsw1"
    header, records = _parse_journal(journal)
    bound = int(manifest["bound_rotate"])
    slack = int(manifest["slack"])
    included: list[dict] = []
    dropped = 0
    if _journal_included(header["rotate_gen"], bound, slack):
        for rec in records:
            if _mask_ok(rec["action_mask"], effective):
                included.append({**rec, "rotate_gen": header["rotate_gen"]})
            else:
                dropped += 1
    else:
        dropped = len(records)
    return included, dropped, manifest


def _merge_included(profile: str) -> tuple[list[tuple[dict, str]], int, dict, int]:
    manifest = _load_manifest(profile)
    effective = _effective_mask(profile, manifest)
    paths = sorted((APP_ENV / "fixtures" / profile).glob("*.vsw1"))
    journals = [(p, *_parse_journal(p)) for p in paths]
    bound = journals[-1][1]["bound_rotate"]
    included: list[tuple[dict, str]] = []
    dropped = 0
    for path, header, records in journals:
        journal_file = path.name
        if _journal_included(header["rotate_gen"], bound, header["slack"]):
            for rec in records:
                if _mask_ok(rec["action_mask"], effective):
                    included.append(
                        ({**rec, "rotate_gen": header["rotate_gen"]}, journal_file)
                    )
                else:
                    dropped += 1
        else:
            dropped += len(records)
    return included, dropped, manifest, bound


def _collect_merge(profile: str) -> tuple[list[dict], int, dict, int]:
    included, dropped, manifest, bound = _merge_included(profile)
    merged: dict[tuple[int, int], tuple[int, str, dict]] = {}
    order: list[tuple[int, int]] = []
    for rec, journal_file in included:
        key = (rec["scope_id"], rec["action_mask"])
        cur = merged.get(key)
        if cur is None:
            order.append(key)
            merged[key] = (rec["rotate_gen"], journal_file, rec)
        elif rec["rotate_gen"] > cur[0]:
            merged[key] = (rec["rotate_gen"], journal_file, rec)
        elif rec["rotate_gen"] == cur[0] and journal_file > cur[1]:
            merged[key] = (rec["rotate_gen"], journal_file, rec)
    final = [merged[key][2] for key in order]
    return final, dropped, manifest, bound


def _digest_from_records(records: list[dict]) -> str:
    buf = b"".join(r["payload"] for r in records)
    return f"{_roll(buf):016x}"


def rebuild_volsweep() -> None:
    subprocess.run(
        "cd /app/environment && cargo build --release",
        shell=True,
        check=True,
    )


def run_cli(workflow: str, profile: str) -> None:
    subprocess.run(
        [VOLSWEEP_BIN, workflow, profile],
        check=True,
    )


def wipe_output() -> None:
    out = Path("/app/output")
    if out.exists():
        shutil.rmtree(out)
    Path("/app/state").mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session", autouse=True)
def _build() -> None:
    rebuild_volsweep()


@pytest.fixture()
def rebuild_alpha() -> dict:
    wipe_output()
    run_cli("rebuild", "site-alpha")
    return json.loads(LEDGER.read_text())


@pytest.fixture()
def merge_beta() -> dict:
    wipe_output()
    run_cli("merge", "site-beta")
    return json.loads(LEDGER.read_text())


def test_r0_regen_harness(rebuild_alpha: dict) -> None:
    """Rebuild emits a ledger with required top-level fields."""
    assert rebuild_alpha["profile"] == "site-alpha"
    assert rebuild_alpha["workflow"] == "rebuild"
    assert isinstance(rebuild_alpha.get("included_records"), int)
    assert isinstance(rebuild_alpha.get("windows"), list)


def test_r1_inclusion_counts(rebuild_alpha: dict) -> None:
    """Rebuild inclusion and drop counts match manifest cutoff and mask rules."""
    included, dropped, _ = _collect_rebuild("site-alpha")
    assert rebuild_alpha["included_records"] == len(included)
    assert rebuild_alpha["dropped_records"] == dropped


def test_r2_time_aggregates(rebuild_alpha: dict) -> None:
    """Time-segment rows match independent rollup for site-alpha."""
    included, _, manifest = _collect_rebuild("site-alpha")
    width = _resolve_width("site-alpha", manifest)
    assert rebuild_alpha["windows"] == _rollup(included, width)


def test_r3_negative_min(rebuild_alpha: dict) -> None:
    """size_min preserves negative deltas (not seeded to zero)."""
    for row in rebuild_alpha["windows"]:
        if row["count"] >= 2:
            assert row["size_min"] <= 0


def test_r4_rebuild_digest(rebuild_alpha: dict) -> None:
    """Rebuild digest rolls concatenated included payloads."""
    included, _, _ = _collect_rebuild("site-alpha")
    assert rebuild_alpha["rebuild_digest"] == _digest_from_records(included)


def test_r5_live_width_fallback() -> None:
    """Probe reports manifest width when cache generation is stale."""
    wipe_output()
    run_cli("probe", "site-alpha")
    snap = json.loads(PROBE.read_text())
    manifest = _load_manifest("site-alpha")
    assert snap["cache_width_ms"] == int(manifest["window_width_ms"])


def test_r6_persist_meta(rebuild_alpha: dict) -> None:
    """Scope state tracks manifest gen, scope count, and max included rotate_gen."""
    included, _, manifest = _collect_rebuild("site-alpha")
    state = json.loads(STATE.read_text())
    assert state["manifest_gen"] == manifest["manifest_gen"]
    assert state["scope_count"] == len(included)
    assert state["last_rotate_gen"] == max(r["rotate_gen"] for r in included)


def test_r7_inclusive_gen(rebuild_alpha: dict) -> None:
    """Journal at rotate_gen == bound + slack is included."""
    header, _ = _parse_journal(APP_ENV / "fixtures/site-alpha/alpha.vsw1")
    manifest = _load_manifest("site-alpha")
    assert header["rotate_gen"] == manifest["bound_rotate"] + manifest["slack"]
    assert rebuild_alpha["included_records"] > 0


def test_r8_rebuild_deterministic() -> None:
    """Repeated rebuild produces identical ledger JSON."""
    wipe_output()
    run_cli("rebuild", "site-alpha")
    first = LEDGER.read_text()
    run_cli("rebuild", "site-alpha")
    assert LEDGER.read_text() == first


def test_r9_regen_after_output_wipe(rebuild_alpha: dict) -> None:
    """Ledger regenerates after output directory wipe."""
    wipe_output()
    run_cli("rebuild", "site-alpha")
    assert json.loads(LEDGER.read_text())["included_records"] == rebuild_alpha["included_records"]


def test_m0_workflow_shape(merge_beta: dict) -> None:
    """Merge workflow emits merge digest and profile."""
    assert merge_beta["workflow"] == "merge"
    assert merge_beta["profile"] == "site-beta"
    assert merge_beta["merge_digest"] is not None


def test_m1_cross_journal_time_rows(merge_beta: dict) -> None:
    """Multi-journal ledger rows use profile-scoped width across journals."""
    final, _, manifest, _ = _collect_merge("site-beta")
    width = _resolve_width("site-beta", manifest)
    assert merge_beta["windows"] == _rollup(final, width)


def test_m2_workflow_digest(merge_beta: dict) -> None:
    """Merge digest uses deduped included payloads in first-seen key order."""
    final, _, _, _ = _collect_merge("site-beta")
    assert merge_beta["merge_digest"] == _digest_from_records(final)


def test_m3_persist_meta(merge_beta: dict) -> None:
    """Merge scope state uses max included journal generation."""
    final, _, _, _ = _collect_merge("site-beta")
    state = json.loads(STATE.read_text())
    assert state["scope_count"] == len(final)
    assert state["last_rotate_gen"] == max(r["rotate_gen"] for r in final)
    assert merge_beta["included_records"] == len(final)


def test_m4_dropped_totals(merge_beta: dict) -> None:
    """Merge dropped count reflects ineligible or masked records only."""
    _, dropped, _, _ = _collect_merge("site-beta")
    assert merge_beta["dropped_records"] == dropped


def test_m5_last_journal_bound(merge_beta: dict) -> None:
    """Merge eligibility uses bound_rotate from lexicographically last journal."""
    paths = sorted((APP_ENV / "fixtures/site-beta").glob("*.vsw1"))
    last_header, _ = _parse_journal(paths[-1])
    final, dropped, manifest, bound = _collect_merge("site-beta")
    assert bound == last_header["bound_rotate"]
    assert merge_beta["included_records"] == len(final)


def test_m6_deterministic() -> None:
    """Merge is deterministic across consecutive runs."""
    wipe_output()
    run_cli("merge", "site-beta")
    first = LEDGER.read_text()
    run_cli("merge", "site-beta")
    assert LEDGER.read_text() == first


def test_m7_slack_per_journal(merge_beta: dict) -> None:
    """Merge excludes journals whose rotate_gen exceeds bound plus header slack."""
    final, _, _, _ = _collect_merge("site-beta")
    assert merge_beta["included_records"] == len(final)
    assert all(r["rotate_gen"] == 5 for r in final if r["scope_id"] != 10 or r["action_mask"] != 0x1)


def test_p1_preserve_overlap(rebuild_alpha: dict) -> None:
    """PRESERVE-marked record is included when stripped bits overlap effective mask."""
    included, _, _ = _collect_rebuild("site-alpha")
    assert rebuild_alpha["included_records"] == len(included)
    assert any(r["scope_id"] == 8 for r in included)


def test_p2_duplicate_prefers_newer(merge_beta: dict) -> None:
    """Duplicate scope_id/action_mask keeps the entry with higher rotate_gen."""
    assert merge_beta["workflow"] == "merge"
    final, _, _, _ = _collect_merge("site-beta")
    included, _, _, _ = _merge_included("site-beta")
    dup_key = next(
        key
        for key, count in Counter((r[0]["scope_id"], r[0]["action_mask"]) for r in included).items()
        if count > 1
        and len({r[0]["rotate_gen"] for r in included if (r[0]["scope_id"], r[0]["action_mask"]) == key}) > 1
    )
    scope_id, mask = dup_key
    dup = [r for r in final if r["scope_id"] == scope_id and r["action_mask"] == mask]
    assert len(dup) == 1
    assert dup[0]["payload"] == b"newgen"
    assert dup[0]["rotate_gen"] == max(
        r[0]["rotate_gen"] for r in included if (r[0]["scope_id"], r[0]["action_mask"]) == dup_key
    )


def test_p5_merge_tie_prefers_later_journal(merge_beta: dict) -> None:
    """Equal rotate_gen duplicates prefer the lexicographically later journal filename."""
    final, _, _, _ = _collect_merge("site-beta")
    rec = next(r for r in final if r["scope_id"] == 21 and r["action_mask"] == 0x2)
    assert rec["payload"] == b"later"
    included, _, _, _ = _merge_included("site-beta")
    tied = [
        journal
        for item, journal in included
        if item["scope_id"] == 21 and item["action_mask"] == 0x2 and item["rotate_gen"] == 5
    ]
    assert len(tied) >= 2
    assert max(tied) == "beta-c.vsw1"


def test_p3_carry_seq_gap(rebuild_alpha: dict) -> None:
    """seq_gap_sum includes carry-over from the previous time segment."""
    included, _, manifest = _collect_rebuild("site-alpha")
    width = _resolve_width("site-alpha", manifest)
    expected = _rollup(included, width)
    bucket_5000 = next(row for row in expected if row["start_ms"] == 5000)
    assert bucket_5000["seq_gap_sum"] >= 5


def test_p4_probe_profile_bits() -> None:
    """Probe reports profile-adjusted effective_mask."""
    wipe_output()
    run_cli("probe", "site-alpha")
    snap = json.loads(PROBE.read_text())
    manifest = _load_manifest("site-alpha")
    assert snap["effective_mask"] == _effective_mask("site-alpha", manifest)


def test_mutation_profile_tightens_inclusion() -> None:
    """Tightening profile mask reduces included records on rebuild."""
    overlay_path = APP_ENV / "ops/overlays/site-alpha.json"
    original = overlay_path.read_text()
    try:
        data = json.loads(original)
        data["mask"] = 0x0001
        overlay_path.write_text(json.dumps(data, indent=2) + "\n")
        wipe_output()
        run_cli("rebuild", "site-alpha")
        reg = json.loads(LEDGER.read_text())
        assert reg["included_records"] == 2
    finally:
        overlay_path.write_text(original)
        rebuild_volsweep()

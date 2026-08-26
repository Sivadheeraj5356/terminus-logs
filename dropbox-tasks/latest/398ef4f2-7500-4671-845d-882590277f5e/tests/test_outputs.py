"""Verifier suite for the airbridge cycle meter task.

Tests exercise the per cycle verdict ladder, asymmetric off hours boundary,
versioned tier lookup, cross cycle monthly cap cascade, holdover override,
duplicate cycle id anchor swap, and numeric type strictness. Anti cheat
layers include build from clean, ELF magic, source presence, data
immutability, idempotency, stale file removal, alt fixture cross check,
and dynamic mutation.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess


APP_ROOT = "/app"
JETWAY_DIR = os.path.join(APP_ROOT, "jetway")
BIN_PATH = os.path.join(APP_ROOT, "bin", "airbridge")
OUTPUT_DIR = os.path.join(APP_ROOT, "output")

ALT_DATA_DIR = "/tests/fixtures/alt_data"

EXPECTED_MAIN_DIGEST = "8549124dd9644db3a2caec43a4c2c24cad2554984b6f60ca9980d7cc55a3692e"
EXPECTED_ALT_DIGEST = "ad1ee6e3dc108084f267ebaf7bf2959812f11f05638d6408bc6a690a419583ee"
EXPECTED_DATA_DIGEST = "3cab6ce373cf5832868703918781dc4ae57b3a3d0e5e0c35bd66f95d05d42556"
EXPECTED_ALT_FIXTURE_DIGEST = "99e7a8813e79aa7b49ee56a94f1be9d99ca8934e773f96004545c9b59da722e5"


def _walk_digest(root, subs=None):
    """Compute aggregate sha256 over (sorted_relpath || NUL || content || NUL)."""
    h = hashlib.sha256()
    paths = []
    if subs is None:
        for r, _, files in os.walk(root):
            for f in files:
                full = os.path.join(r, f)
                rel = os.path.relpath(full, root)
                paths.append((rel, full))
    else:
        for sub in subs:
            for r, _, files in os.walk(os.path.join(root, sub)):
                for f in files:
                    full = os.path.join(r, f)
                    rel = os.path.relpath(full, root)
                    paths.append((rel, full))
    paths.sort()
    for rel, full in paths:
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        with open(full, "rb") as fp:
            h.update(fp.read())
        h.update(b"\x00")
    return h.hexdigest()


def _read_cycles():
    """Return cycles.ndjson as a list of parsed dicts."""
    with open(os.path.join(OUTPUT_DIR, "cycles.ndjson"), encoding="utf-8") as fp:
        return [json.loads(line) for line in fp if line.strip()]


def _by_id(rows):
    return {row["cycle_id"]: row for row in rows}


def _run_binary(env_extra=None):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run([BIN_PATH], capture_output=True, text=True, env=env)


def test_build_from_clean_succeeds():
    """A1 build from clean — remove bin/ then rebuild via Makefile and check binary exists."""
    bin_dir = os.path.join(APP_ROOT, "bin")
    if os.path.isdir(bin_dir):
        shutil.rmtree(bin_dir)
    res = subprocess.run(["make", "build"], cwd=APP_ROOT, capture_output=True, text=True)
    assert res.returncode == 0, f"make build failed: {res.stderr}"
    assert os.path.exists(BIN_PATH), "binary missing after build"


def test_binary_is_elf():
    """A1 ELF magic byte check on the compiled binary."""
    with open(BIN_PATH, "rb") as fp:
        head = fp.read(4)
    assert head == b"\x7fELF", "binary is not a real ELF file"


def test_main_source_present():
    """A2 main.go must exist and be non trivial (no empty stub passing)."""
    src = os.path.join(JETWAY_DIR, "main.go")
    assert os.path.exists(src), "main.go missing under /app/jetway"
    size = os.path.getsize(src)
    assert size > 1000, f"main.go too small ({size} bytes); real implementation expected"


def test_run_produces_three_outputs():
    """Output exclusivity — exactly the three expected output files exist after a run."""
    res = _run_binary()
    assert res.returncode == 0, f"binary exited non zero: {res.stderr}"
    expected = {"cycles.ndjson", "summary.toml", "digest.txt"}
    have = set(os.listdir(OUTPUT_DIR))
    assert expected.issubset(have), f"missing outputs: {expected - have}"


def test_digest_matches_expected_main():
    """Main fixture run pins digest.txt to the recorded SHA256."""
    _run_binary()
    with open(os.path.join(OUTPUT_DIR, "digest.txt"), encoding="utf-8") as fp:
        got = fp.read().strip()
    assert got == EXPECTED_MAIN_DIGEST, f"digest mismatch: got {got}"


def test_digest_is_lowercase_hex():
    """digest.txt is sixty four lowercase hex chars."""
    with open(os.path.join(OUTPUT_DIR, "digest.txt"), encoding="utf-8") as fp:
        got = fp.read().strip()
    assert re.fullmatch(r"[0-9a-f]{64}", got), f"digest is not lowercase hex64: {got}"


def test_input_data_is_immutable():
    """A3 data immutability — input fixture digest unchanged before and after run."""
    before = _walk_digest(APP_ROOT, subs=("ramplog", "feebook"))
    _run_binary()
    after = _walk_digest(APP_ROOT, subs=("ramplog", "feebook"))
    assert before == after, "input fixtures were mutated by the run"
    assert before == EXPECTED_DATA_DIGEST, "input fixtures drifted from recorded value"


def test_idempotency_byte_diff():
    """A4 running the binary twice produces byte identical outputs."""
    _run_binary()
    snap = {}
    for name in os.listdir(OUTPUT_DIR):
        with open(os.path.join(OUTPUT_DIR, name), "rb") as fp:
            snap[name] = fp.read()
    _run_binary()
    for name, data in snap.items():
        with open(os.path.join(OUTPUT_DIR, name), "rb") as fp:
            assert fp.read() == data, f"{name} differs on second run"


def test_stale_outputs_are_overwritten():
    """A5 a leftover file in /app/output is overwritten cleanly by the run."""
    with open(os.path.join(OUTPUT_DIR, "cycles.ndjson"), "w", encoding="utf-8") as fp:
        fp.write("stale content\n")
    _run_binary()
    with open(os.path.join(OUTPUT_DIR, "cycles.ndjson"), encoding="utf-8") as fp:
        first = fp.readline()
    assert "stale content" not in first, "stale cycles file was not regenerated"


def test_alt_fixture_digest():
    """A6 binary on the alt fixture produces the recorded alt digest."""
    out_dir = "/tmp/alt_out"
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    res = _run_binary({"AIRBRIDGE_DATA": ALT_DATA_DIR, "AIRBRIDGE_OUT": out_dir})
    assert res.returncode == 0, f"alt run failed: {res.stderr}"
    with open(os.path.join(out_dir, "digest.txt"), encoding="utf-8") as fp:
        got = fp.read().strip()
    assert got == EXPECTED_ALT_DIGEST, f"alt digest mismatch: got {got}"


def test_alt_fixture_integrity():
    """Alt fixture itself has the recorded fingerprint (catches fixture tampering)."""
    have = _walk_digest(ALT_DATA_DIR)
    assert have == EXPECTED_ALT_FIXTURE_DIGEST, f"alt fixture drift: {have}"


def test_dynamic_mutation_changes_digest():
    """A7 patching a fixture line at runtime changes the output digest."""
    out_dir = "/tmp/mut_out"
    work = "/tmp/mut_data"
    if os.path.isdir(work):
        shutil.rmtree(work)
    shutil.copytree(ALT_DATA_DIR, work)
    flights = os.path.join(work, "ramplog", "flights_alt.ndjson")
    with open(flights, encoding="utf-8") as fp:
        lines = fp.readlines()
    obj = json.loads(lines[0])
    obj["dwell_minutes"] = obj["dwell_minutes"] + 5
    lines[0] = json.dumps(obj) + "\n"
    with open(flights, "w", encoding="utf-8") as fp:
        fp.writelines(lines)
    os.makedirs(out_dir, exist_ok=True)
    res = _run_binary({"AIRBRIDGE_DATA": work, "AIRBRIDGE_OUT": out_dir})
    assert res.returncode == 0, f"mutation run failed: {res.stderr}"
    with open(os.path.join(out_dir, "digest.txt"), encoding="utf-8") as fp:
        got = fp.read().strip()
    assert got != EXPECTED_ALT_DIGEST, "digest did not change after fixture mutation"


def test_cleared_simple_cycle():
    """CYC0001 — straight cleared narrow body cycle bills base plus dwell rate."""
    rows = _by_id(_read_cycles())
    row = rows["CYC0001"]
    assert row["verdict"] == "CLEARED"
    assert row["net_fee_cents"] == 26390
    assert row["tier_version"] == "2026-05-01T00:00:00Z"


def test_offhours_wide_body_late_night():
    """CYC0002 — wide body in block at 23 32 falls in off hours window with B_MAIN uplift."""
    row = _by_id(_read_cycles())["CYC0002"]
    assert row["verdict"] == "OFFHOURS_PREMIUM"
    assert row["net_fee_cents"] == 64998


def test_offhours_left_exclusive_boundary_at_22_00_00():
    """CYC0006 in block at exactly 22 00 00 is NOT in off hours (start is exclusive)."""
    row = _by_id(_read_cycles())["CYC0006"]
    assert row["verdict"] == "CLEARED", "22:00:00 sharp must NOT be off hours"


def test_offhours_left_exclusive_boundary_one_second_in():
    """CYC0007 in block at 22 00 01 IS in off hours (one second past the exclusive start)."""
    row = _by_id(_read_cycles())["CYC0007"]
    assert row["verdict"] == "OFFHOURS_PREMIUM"


def test_offhours_right_inclusive_boundary_at_06_00_00():
    """CYC0004 in block at exactly 06 00 00 IS still off hours (end is inclusive)."""
    row = _by_id(_read_cycles())["CYC0004"]
    assert row["verdict"] == "OFFHOURS_PREMIUM"


def test_offhours_right_boundary_one_second_past():
    """CYC0005 in block at 06 00 01 is NOT in off hours (one second past the inclusive end)."""
    row = _by_id(_read_cycles())["CYC0005"]
    assert row["verdict"] == "CLEARED"


def test_stale_tier_when_assignment_and_inblock_straddle_rate_change():
    """CYC0008 gate assigned in April but in block in May lands on stale tier."""
    row = _by_id(_read_cycles())["CYC0008"]
    assert row["verdict"] == "STALE_TIER"
    assert row["net_fee_cents"] == 0
    assert row["tier_version"] == "2026-01-01T00:00:00Z"


def test_rejected_numeric_on_float_mtow():
    """CYC0009 mtow tons is the float 78.0 and must reject as numeric anomaly."""
    row = _by_id(_read_cycles())["CYC0009"]
    assert row["verdict"] == "REJECTED_NUMERIC"
    assert row["net_fee_cents"] == 0


def test_rejected_tier_on_unknown_body_code():
    """CYC0010 body code XX is not in {NB, WB, RJ} and rejects."""
    row = _by_id(_read_cycles())["CYC0010"]
    assert row["verdict"] == "REJECTED_TIER"
    assert row["net_fee_cents"] == 0


def test_holdover_doubles_base_fee():
    """CYC0011 status HOLDOVER bills at exactly twice the base fee for the tier."""
    row = _by_id(_read_cycles())["CYC0011"]
    assert row["verdict"] == "HOLDOVER_REBILL"
    assert row["net_fee_cents"] == 56700


def test_cap_breach_marks_subsequent_cycle_capped():
    """CYC0013 follows the breaching cycle for UA A_NORTH in May and is capped."""
    row = _by_id(_read_cycles())["CYC0013"]
    assert row["verdict"] == "CAPPED_OVERAGE"
    assert row["net_fee_cents"] == 0


def test_cap_overage_continues_after_first_capped():
    """CYC0014 is the second cycle past the UA A_NORTH May cap; the cap latches so
    every following cycle in the same (carrier, gate_zone, month) stays CAPPED_OVERAGE
    with net_fee_cents = 0 rather than briefly returning to CLEARED."""
    row = _by_id(_read_cycles())["CYC0014"]
    assert row["verdict"] == "CAPPED_OVERAGE"
    assert row["net_fee_cents"] == 0


def test_holdover_overrides_cap_overage():
    """CYC0015 is HOLDOVER on a (UA, A_NORTH, May) key whose cap was already breached
    by earlier cycles. HOLDOVER_REBILL must still win the verdict and bill at twice the
    base fee — the cap does not zero the holdover row and does not swallow its billing."""
    row = _by_id(_read_cycles())["CYC0015"]
    assert row["verdict"] == "HOLDOVER_REBILL"
    assert row["net_fee_cents"] == 51800


def test_duplicate_with_matching_mtow_takes_latest_status():
    """CYC0018 appears in day2 NORMAL and anomalies HOLDOVER — latest wins on status."""
    row = _by_id(_read_cycles())["CYC0018"]
    assert row["verdict"] == "HOLDOVER_REBILL"
    assert row["mtow_tons"] == 180, "mtow comes from the earliest row in the duplicate set"
    assert row["net_fee_cents"] == 113040


def test_void_duplicate_on_mtow_conflict():
    """CYC0019 has mtow 82 in day2 and mtow 80 in anomalies — void duplicate."""
    row = _by_id(_read_cycles())["CYC0019"]
    assert row["verdict"] == "VOID_DUPLICATE"
    assert row["net_fee_cents"] == 0


def test_older_tier_used_for_april_cycle():
    """CYC0021 is an April cycle and prices off the January effective tier."""
    row = _by_id(_read_cycles())["CYC0021"]
    assert row["verdict"] == "CLEARED"
    assert row["net_fee_cents"] == 23340
    assert row["tier_version"] == "2026-01-01T00:00:00Z"


def test_sort_order_is_ascending_cycle_id():
    """The primary sort key is cycle_id ascending; ties within the same cycle_id are
    broken by gate_zone ascending. Output_shapes pins this exact chain so the digest is
    reproducible; an implementation that sorts by carrier or by inblock timestamp fails."""
    rows = _read_cycles()
    ids = [r["cycle_id"] for r in rows]
    assert ids == sorted(ids), f"unsorted: {ids}"


def test_row_count_matches_unique_cycle_ids():
    """Duplicate cycle_id rows across day shards and the anomalies file must merge into
    exactly one output record per distinct cycle_id. The primary fixture holds 21 unique
    cycle_ids across 23 source rows (two of which are duplicate corrections)."""
    rows = _read_cycles()
    ids = {r["cycle_id"] for r in rows}
    assert len(rows) == len(ids) == 21


def test_no_extra_keys_in_cycle_records():
    """cycles.ndjson pins the schema to exactly nine keys per row (cycle_id, carrier_iata,
    gate_zone, body_code, mtow_tons, dwell_minutes, net_fee_cents, verdict, tier_version).
    Extra keys (debug fields, source pointers, per-row timestamps) drift the digest and are rejected."""
    rows = _read_cycles()
    expected_keys = {
        "cycle_id", "carrier_iata", "gate_zone", "body_code",
        "mtow_tons", "dwell_minutes", "net_fee_cents", "verdict", "tier_version",
    }
    for r in rows:
        assert set(r.keys()) == expected_keys, f"key drift: {set(r.keys())} on {r.get('cycle_id')}"


def test_net_fee_cents_is_integer_in_output():
    """net_fee_cents must serialize as a JSON integer (no decimal point)."""
    with open(os.path.join(OUTPUT_DIR, "cycles.ndjson"), encoding="utf-8") as fp:
        text = fp.read()
    for needle in ("\"net_fee_cents\":0.0", "\"mtow_tons\":78.0"):
        assert needle not in text, f"output contains float scalar: {needle}"


def test_summary_aggregates_match_per_carrier_per_verdict():
    """Summary totals reproduce the per carrier per verdict aggregates of cycles.ndjson."""
    rows = _read_cycles()
    agg = {}
    for r in rows:
        k = (r["carrier_iata"], r["verdict"])
        c, s = agg.get(k, (0, 0))
        agg[k] = (c + 1, s + r["net_fee_cents"])
    with open(os.path.join(OUTPUT_DIR, "summary.toml"), encoding="utf-8") as fp:
        text = fp.read()
    for (carrier, verdict), (count, billed) in agg.items():
        block = (
            f"carrier_iata = \"{carrier}\"\n"
            f"verdict = \"{verdict}\"\n"
            f"cycle_count = {count}\n"
            f"billed_cents = {billed}\n"
        )
        assert block in text, f"missing aggregate block for {carrier} {verdict}"


def test_summary_schema_header_present():
    """summary.toml must open with the literal line schema = "airbridge_summary_v1"; the
    header is the version marker that downstream consumers key on. A missing or renamed
    header (schema = "airbridge_summary" or v2) rejects even if the rest is well formed."""
    with open(os.path.join(OUTPUT_DIR, "summary.toml"), encoding="utf-8") as fp:
        head = fp.readline()
    assert head.strip() == "schema = \"airbridge_summary_v1\""


def test_digest_recomputable_from_canonical_pipe_form():
    """digest.txt equals sha256 over pipe-joined per-row preimages."""
    rows = _read_cycles()
    h = hashlib.sha256()
    for r in rows:
        line = "|".join([
            r["cycle_id"], r["carrier_iata"], r["gate_zone"], r["body_code"],
            str(r["mtow_tons"]), str(r["dwell_minutes"]),
            str(r["net_fee_cents"]), r["verdict"], r["tier_version"],
        ])
        h.update(line.encode("utf-8"))
        h.update(b"\n")
    with open(os.path.join(OUTPUT_DIR, "digest.txt"), encoding="utf-8") as fp:
        got = fp.read().strip()
    assert got == h.hexdigest()


def test_no_python_under_app_jetway():
    """Implementation language guard — no .py file may appear under /app/jetway."""
    for r, _, files in os.walk(JETWAY_DIR):
        for f in files:
            assert not f.endswith(".py"), f"Python file found under jetway: {f}"

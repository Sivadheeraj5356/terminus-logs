"""Verifier for chain-verify-reload-skew cross-module coherence."""

import csv
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

APP = Path("/app")
_CARGO = shutil.which("cargo") or "/usr/local/cargo/bin/cargo"
PROBE_BIN = APP / "target" / "release" / "probe"
WAVE_SPEC = APP / "data" / "rotation_spec.txt"
TRACE = APP / "output" / "trace.json"
READOUT = APP / "output" / "readout.csv"
CASE_TAGS = ["cold_tick", "link_ticks", "rotate_hold", "twin_leaf"]
DEFAULT_CHAIN_BUMPS = ((3, 1), (5, 2), (7, 1))


def _consult_expected(carry: int, key: int, gate_slice: int = 1) -> bool:
    return (((carry + gate_slice) ^ key) & 1) == 0


def _consult_inverted_near_miss(carry: int, key: int, gate_slice: int = 1) -> bool:
    """Plausible wrong polarity: denial when the low XOR bit is one."""
    return (((carry + gate_slice) ^ key) & 1) == 1


def _run_probe(extra_env: dict[str, str]) -> str:
    env = os.environ.copy()
    env.update(extra_env)
    proc = subprocess.run(
        [PROBE_BIN],
        cwd=APP,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _probe_int(extra_env: dict[str, str]) -> int:
    return int(_run_probe(extra_env))


def _probe_bool(extra_env: dict[str, str]) -> bool:
    return _run_probe(extra_env) == "1"


def _load_rotation_spec() -> dict[str, Any]:
    return json.loads(WAVE_SPEC.read_text())


def _bumps_env(bumps: list[tuple[int, int]]) -> str:
    return ";".join(f"{a},{b}" for a, b in bumps)


def _probe_chain_ticks(bumps: list[tuple[int, int]]) -> list[int]:
    ticks = _run_probe(
        {"TB_PROBE": "over_ticks", "TB_BUMP_CHAIN": _bumps_env(bumps)}
    ).split(",")
    return [int(x) for x in ticks if x]


def _cargo_build() -> None:
    subprocess.run(
        [
            "cargo",
            "build",
            "--release",
            "--bins",
            "--manifest-path",
            "/app/environment/Cargo.toml",
        ],
        cwd="/app",
        check=True,
    )


def _run_chainlab() -> None:
    subprocess.run(["/app/bin/run_chainlab"], cwd=APP, check=True)


def _case(bundle: dict[str, Any], tag: str) -> dict[str, Any]:
    return next(c for c in bundle["cases"] if c["tag"] == tag)


@pytest.fixture(scope="module")
def _build_and_run() -> None:
    _cargo_build()
    _run_chainlab()


@pytest.fixture(scope="module")
def bundle(_build_and_run: None) -> dict[str, Any]:
    return json.loads(TRACE.read_text())


def test_cold_ceiling_follows_operand_sum(_build_and_run: None) -> None:
    """Promotion ceiling after a cold bump must track operand sum."""
    a, b = 9, 1
    vol = _probe_int({"TB_PROBE": "cold", "TB_BUMP_A": str(a), "TB_BUMP_B": str(b)})
    assert vol == a + b


def test_token_carry_tracks_live_sequence_after_bump(_build_and_run: None) -> None:
    """Bind carry must track live promotion after a bump."""
    vol = _probe_int({"TB_PROBE": "cold", "TB_BUMP_A": "9", "TB_BUMP_B": "1"})
    carry = _probe_int(
        {
            "TB_PROBE": "bind",
            "TB_BUMP_A": "9",
            "TB_BUMP_B": "1",
            "TB_SEED": "0",
            "TB_BIND_P": "4",
            "TB_BIND_Q": "0",
        }
    )
    assert carry == vol
    assert carry != (4 ^ vol)


def test_consult_denied_matches_carry_key_formula(_build_and_run: None) -> None:
    """Consult refusal must follow the gate formula in contract.md."""
    samples = [(10, 11, True), (10, 10, False), (7, 5, False), (19, 4, True)]
    for carry, key, want in samples:
        got = _probe_bool({"TB_PROBE": "consult", "TB_CARRY": str(carry), "TB_KEY": str(key)})
        assert got is want
        assert got is _consult_expected(carry, key)


def test_consult_respects_gate_slice_env(_build_and_run: None) -> None:
    """Consult refusal must honor the active gate slice byte."""
    carry, key = 10, 11
    for gate_slice in (1, 2, 3):
        got = _probe_bool(
            {
                "TB_PROBE": "consult",
                "TB_CARRY": str(carry),
                "TB_KEY": str(key),
                "TB_GATE_SLICE": str(gate_slice),
            }
        )
        assert got is _consult_expected(carry, key, gate_slice)


def test_consult_denied_flips_when_key_changes_at_fixed_carry(_build_and_run: None) -> None:
    """Same carry with different keys must change consult refusal."""
    carry = 10
    denied_a = _probe_bool({"TB_PROBE": "consult", "TB_CARRY": str(carry), "TB_KEY": "11"})
    denied_b = _probe_bool({"TB_PROBE": "consult", "TB_CARRY": str(carry), "TB_KEY": "10"})
    assert denied_a != denied_b


def test_surface_denial_follows_pulled_not_inverted_text_a(_build_and_run: None) -> None:
    """Readout row mapping must follow the harness pulled view."""
    assert _probe_bool({"TB_PROBE": "row", "TB_PULLED": "1", "TB_TEXT_A": "0", "TB_TEXT_B": "0"})
    assert not _probe_bool({"TB_PROBE": "row", "TB_PULLED": "0", "TB_TEXT_A": "1", "TB_TEXT_B": "0"})


def test_rotate_hold_held_carry_stays_below_promoted_vol(_build_and_run: None) -> None:
    """rotate_hold wire probe carry must stay below promoted volume."""
    vol_s, carry_s = _run_probe({"TB_PROBE": "wire"}).split(",")
    vol = int(vol_s)
    carry = int(carry_s)
    assert carry < vol
    assert vol > 0


def test_link_ticks_blk_marks_strictly_increase(_build_and_run: None) -> None:
    """link_ticks cadence must publish strictly increasing blk_marks samples."""
    ticks = [int(x) for x in _run_probe({"TB_PROBE": "over_ticks"}).split(",") if x]
    assert len(ticks) >= 2
    for i in range(1, len(ticks)):
        assert ticks[i] > ticks[i - 1]
    alt = [int(x) for x in _run_probe(
        {"TB_PROBE": "over_ticks", "TB_BUMP_CHAIN": "4,1;6,2;8,1"}
    ).split(",") if x]
    assert ticks != alt


def test_twin_leaf_first_token_stays_prepromotion(_build_and_run: None) -> None:
    """twin_leaf first wire carry must remain below the first promotion tick."""
    carry_s, vol_s = _run_probe({"TB_PROBE": "dual"}).split(",")
    carry = int(carry_s)
    vol = int(vol_s)
    assert carry < vol


def test_ceil_fetch_max_respects_ceiling(_build_and_run: None) -> None:
    """Promotion ceiling must advance when a larger acc value is published."""
    low = _probe_int({"TB_PROBE": "cold", "TB_BUMP_A": "3", "TB_BUMP_B": "1"})
    high = _probe_int({"TB_PROBE": "cold", "TB_BUMP_A": "40", "TB_BUMP_B": "2"})
    assert high > low


def _expected_chain_ticks(bumps: list[tuple[int, int]]) -> list[int]:
    """Independent promotion-ceiling model: running acc sum with monotonic vol peak."""
    acc = 0
    vol = 0
    ticks: list[int] = []
    for a, b in bumps:
        acc = (acc + a + b) & ((1 << 64) - 1)
        vol = max(vol, acc)
        ticks.append(vol)
    return ticks


def test_vol_ceiling_monotonic_under_downward_publish(_build_and_run: None) -> None:
    """Promotion ceiling must follow cumulative acc and never retreat on a smaller bump."""
    bumps = [(50, 3), (2, 1)]
    ticks = _probe_chain_ticks(bumps)
    expected = _expected_chain_ticks(bumps)
    assert ticks == expected
    assert ticks[1] >= ticks[0]


def test_bind_carry_respects_session_last_carry(_build_and_run: None) -> None:
    """Bind carry must fold session carry forward, not bind operands alone."""
    bump_a, bump_b = 4, 1
    vol = bump_a + bump_b
    with_seed = _probe_int(
        {
            "TB_PROBE": "bind",
            "TB_BUMP_A": str(bump_a),
            "TB_BUMP_B": str(bump_b),
            "TB_SEED": "9",
            "TB_BIND_P": "2",
            "TB_BIND_Q": "0",
        }
    )
    fresh = _probe_int(
        {
            "TB_PROBE": "bind",
            "TB_BUMP_A": str(bump_a),
            "TB_BUMP_B": str(bump_b),
            "TB_SEED": "0",
            "TB_BIND_P": "2",
            "TB_BIND_Q": "0",
        }
    )
    assert with_seed == max(9, vol)
    assert fresh == vol


def test_triple_run_chainlab_trace_and_csv_stable() -> None:
    """Three rebuild-and-run cycles must emit byte-identical trace and readout artifacts."""
    _cargo_build()
    snapshots: list[tuple[bytes, bytes]] = []
    for _ in range(3):
        _run_chainlab()
        snapshots.append((TRACE.read_bytes(), READOUT.read_bytes()))
    assert snapshots[0] == snapshots[1] == snapshots[2]


def test_harness_outputs_match_consult_row_and_csv_contract(bundle: dict[str, Any]) -> None:
    """Regenerated harness artifacts must satisfy consult, row, and CSV parity invariants."""
    rows: dict[str, str] = {}
    with READOUT.open(newline="") as handle:
        for row in csv.DictReader(handle):
            rows[row["tag"]] = row["latch_denied"]

    assert list(rows.keys()) == CASE_TAGS
    assert [c["tag"] for c in bundle["cases"]] == CASE_TAGS

    for case in bundle["cases"]:
        tag = case["tag"]
        ticks = case["blk_marks"]
        tries = case["tries"]
        assert tries

        for tr in tries:
            carry = int(tr["carry_at_try"])
            key = int(tr["key"])
            if tag == "cold_tick":
                ch = _load_rotation_spec()["cold_tick"]
                gate_slice = int(ch.get("gate_slice", 1))
                assert tr["latch_denied"] is _consult_expected(carry, key, gate_slice)
            else:
                assert tr["latch_denied"] is _consult_expected(carry, key)

        last = tries[-1]
        pulled = bool(last["latch_denied"])
        row_denied = _probe_bool(
            {
                "TB_PROBE": "row",
                "TB_PULLED": "1" if pulled else "0",
                "TB_TEXT_A": "1" if not pulled else "0",
                "TB_TEXT_B": "0",
            }
        )
        assert row_denied is pulled
        assert rows[tag].lower() == str(pulled).lower()

        if tag == "cold_tick":
            assert int(last["carry_at_try"]) == ticks[0]
        elif tag == "link_ticks":
            assert len(ticks) >= 2
            assert all(ticks[i] > ticks[i - 1] for i in range(1, len(ticks)))
            assert int(last["carry_at_try"]) == ticks[-1]
        elif tag == "rotate_hold":
            assert int(last["carry_at_try"]) <= ticks[-1]
            assert int(last["carry_at_try"]) != ticks[-1]
        elif tag == "twin_leaf":
            assert len(ticks) >= 2
            assert int(tries[0]["carry_at_try"]) < ticks[0]
            assert int(tries[-1]["carry_at_try"]) == ticks[-1]


def test_link_ticks_blk_marks_match_rotation_spec_via_probe(bundle: dict[str, Any]) -> None:
    """link_ticks blk_marks must match live promotion from rotation_spec bumps."""
    spec = _load_rotation_spec()
    bumps = [tuple(pair) for pair in spec["link_ticks"]["bumps"]]
    expected = _probe_chain_ticks(bumps)
    chain = _case(bundle, "link_ticks")
    assert chain["blk_marks"] == expected


def test_link_ticks_first_blk_mark_not_seeded_from_prior_case(bundle: dict[str, Any]) -> None:
    """link_ticks must open its reload frame without inheriting cold_tick peak."""
    spec = _load_rotation_spec()
    bumps = [tuple(pair) for pair in spec["link_ticks"]["bumps"]]
    first_pair = bumps[0]
    chain = _case(bundle, "link_ticks")
    expected_first = _probe_chain_ticks([first_pair])[0]
    assert chain["blk_marks"][0] == expected_first


def test_frame_probe_second_chain_ignores_first_peak(_build_and_run: None) -> None:
    """Frame close/open must zero the generation peak before the second chain."""
    first = [(50, 3), (2, 1)]
    second = [(4, 1), (6, 2)]
    raw = _run_probe(
        {
            "TB_PROBE": "frame",
            "TB_FRAME_A": _bumps_env(first),
            "TB_FRAME_B": _bumps_env(second),
        }
    )
    _left_s, right_s = raw.split("|", 1)
    second_ticks = [int(x) for x in right_s.split(",") if x]
    expected_second = _probe_chain_ticks(second)
    assert second_ticks == expected_second
    assert second_ticks[0] == second[0][0] + second[0][1]
    assert second_ticks[0] < _expected_chain_ticks(first)[0]


def test_row_probe_rejects_xor_blend(_build_and_run: None) -> None:
    """Row mapping must not xor pulled with text_a."""
    pulled = _probe_bool({"TB_PROBE": "row", "TB_PULLED": "1", "TB_TEXT_A": "1", "TB_TEXT_B": "0"})
    assert pulled is True


def test_mutating_rotation_spec_changes_link_ticks_blk_marks() -> None:
    """Editing rotation_spec.txt must change link_ticks blk_marks after run_chainlab reruns."""
    original = WAVE_SPEC.read_text()
    alt_bumps = [(4, 1), (6, 2), (8, 1)]
    try:
        spec = _load_rotation_spec()
        spec["link_ticks"]["bumps"] = [list(pair) for pair in alt_bumps]
        WAVE_SPEC.write_text(json.dumps(spec, indent=2) + "\n")
        _cargo_build()
        _run_chainlab()
        bundle = json.loads(TRACE.read_text())
        chain = _case(bundle, "link_ticks")
        assert chain["blk_marks"] == _probe_chain_ticks(alt_bumps)
        assert chain["blk_marks"] != _probe_chain_ticks(list(DEFAULT_CHAIN_BUMPS))
    finally:
        WAVE_SPEC.write_text(original)


def test_mutating_link_ticks_leaves_cold_tick_blk_marks_stable(_build_and_run: None) -> None:
    """link_ticks bump edits must not rewrite cold_tick promotion samples."""
    original = WAVE_SPEC.read_text()
    alt_bumps = [(4, 1), (6, 2), (8, 1)]
    try:
        spec = _load_rotation_spec()
        cold_before = _case(json.loads(TRACE.read_text()), "cold_tick")["blk_marks"]
        spec["link_ticks"]["bumps"] = [list(pair) for pair in alt_bumps]
        WAVE_SPEC.write_text(json.dumps(spec, indent=2) + "\n")
        _cargo_build()
        _run_chainlab()
        cold_after = _case(json.loads(TRACE.read_text()), "cold_tick")["blk_marks"]
        assert cold_after == cold_before
        ch = spec["cold_tick"]
        expected = _probe_int(
            {
                "TB_PROBE": "cold",
                "TB_BUMP_A": str(ch["bump_a"]),
                "TB_BUMP_B": str(ch["bump_b"]),
            }
        )
        assert cold_after == [expected]
    finally:
        WAVE_SPEC.write_text(original)


def test_mutating_rotation_spec_gate_slice_changes_cold_tick_consult() -> None:
    """Editing cold_tick gate_slice in rotation_spec must change consult refusal after rerun."""
    original = WAVE_SPEC.read_text()
    try:
        spec = _load_rotation_spec()
        spec["cold_tick"]["gate_slice"] = 2
        WAVE_SPEC.write_text(json.dumps(spec, indent=2) + "\n")
        _cargo_build()
        _run_chainlab()
        bundle = json.loads(TRACE.read_text())
        case = _case(bundle, "cold_tick")
        carry = int(case["tries"][0]["carry_at_try"])
        key = int(spec["cold_tick"]["consult_key"])
        assert case["tries"][0]["latch_denied"] is _consult_expected(carry, key, 2)
        assert case["tries"][0]["latch_denied"] is not _consult_expected(carry, key, 1)
    finally:
        WAVE_SPEC.write_text(original)


def test_trace_readout_final_denial_cross_artifact(_build_and_run: None) -> None:
    """Final try latch_denied in trace.json must match readout.csv per tag."""
    bundle = json.loads(TRACE.read_text())
    rows: dict[str, str] = {}
    with READOUT.open(newline="") as handle:
        for row in csv.DictReader(handle):
            rows[row["tag"]] = row["latch_denied"]
    for case in bundle["cases"]:
        tag = case["tag"]
        final_denied = case["tries"][-1]["latch_denied"]
        assert rows[tag].lower() == str(final_denied).lower()
        assert rows[tag].lower() in {"true", "false"}


def test_link_ticks_blk_marks_match_independent_chain_model(bundle: dict[str, Any]) -> None:
    """link_ticks blk_marks must match a Python chain model from rotation_spec bumps."""
    spec = _load_rotation_spec()
    bumps = [tuple(pair) for pair in spec["link_ticks"]["bumps"]]
    expected = _expected_chain_ticks(bumps)
    chain = _case(bundle, "link_ticks")
    assert chain["blk_marks"] == expected
    assert expected[-1] > expected[0]


def test_cold_tick_trace_matches_independent_single_bump_model(bundle: dict[str, Any]) -> None:
    """cold_tick blk_marks must equal the independent single-tick promotion model."""
    spec = _load_rotation_spec()
    ch = spec["cold_tick"]
    expected = ch["bump_a"] + ch["bump_b"]
    cold = _case(bundle, "cold_tick")
    assert cold["blk_marks"] == [expected]
    assert int(cold["tries"][0]["carry_at_try"]) == expected


def test_consult_rejects_inverted_polarity_near_miss(_build_and_run: None) -> None:
    """Consult refusal must not follow the inverted low-bit polarity trap."""
    samples = [(10, 11), (7, 5), (19, 4), (12, 3)]
    for carry, key in samples:
        got = _probe_bool({"TB_PROBE": "consult", "TB_CARRY": str(carry), "TB_KEY": str(key)})
        wrong = _consult_inverted_near_miss(carry, key)
        if _consult_expected(carry, key) != wrong:
            assert got is _consult_expected(carry, key)
            assert got is not wrong


def test_rotate_hold_trace_carry_below_final_blk_mark(bundle: dict[str, Any]) -> None:
    """rotate_hold final try carry must sit strictly below the case generation peak."""
    case = _case(bundle, "rotate_hold")
    peak = case["blk_marks"][-1]
    carry = int(case["tries"][-1]["carry_at_try"])
    assert carry < peak
    assert peak > 0


def test_run_chainlab_fails_without_rotation_spec() -> None:
    """run_chainlab must read rotation_spec.txt instead of emitting a static trace bundle."""
    backup = WAVE_SPEC.read_bytes()
    try:
        WAVE_SPEC.unlink()
        _cargo_build()
        proc = subprocess.run(
            ["/app/bin/run_chainlab"],
            cwd=APP,
            capture_output=True,
            text=True,
        )
        assert proc.returncode != 0
    finally:
        WAVE_SPEC.write_bytes(backup)

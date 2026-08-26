import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

import pytest

ENV = Path("/app/environment")
OUT = Path("/app/output/cmb_out.json")
EV_DIR = ENV / "fixtures" / "ev_bins"
STUB = ENV / "fixtures" / "tmp" / "interim_tally.json"
STATE_PATH = Path("/app/var/lab/settle_state.json")
JOURNAL_PATH = Path("/app/var/lab/pulse_journal.jsonl")
MDL_LAB = "/app/bin/mdl_lab"
HIDDEN_DIR = Path("/tests/fixtures")

MANIFESTS = ("sc_m1", "sc_m2", "sc_m3", "sc_m4", "sc_m5")
PROFILES = ("strict_tick", "loose_tick")
RUN_ORDER = [
    ("sc_m1", "strict_tick"),
    ("sc_m1", "loose_tick"),
    ("sc_m2", "strict_tick"),
    ("sc_m2", "loose_tick"),
    ("sc_m3", "strict_tick"),
    ("sc_m3", "loose_tick"),
    ("sc_m4", "strict_tick"),
    ("sc_m4", "loose_tick"),
    ("sc_m5", "strict_tick"),
    ("sc_m5", "loose_tick"),
]
# Baked pins — not derived from live agent-editable bytes at import time.
PUBLIC_FIXTURE_SHA256 = {
    "scenarios/sc_m1.json": "6bbfd6692ead35299372e8a0371e16052b0cfe46afa2b493055b53b572ad87ad",
    "scenarios/sc_m2.json": "080fd77b67bab45fa556e2056fc2f53303e9190b928829bb923b1c42676185ec",
    "scenarios/sc_m3.json": "db4b053d94152cb6502e2e783828fad8a64f8b154a438ad15103e02e025a14fd",
    "scenarios/sc_m4.json": "a651ad4a6123b6d3844c7fa4b629d9e6624da64267672790ba880757a7b32744",
    "scenarios/sc_m5.json": "7a476529d7ef0d974cff16f5600fe7a1c75613bf919afe4b73c582f2787a360f",
    "scenarios/sweep_m0.json": "9d4e126ddd2c5ec16a0c13d24276c8be359fbd445f6b0ebf8f07b721feac57f3",
    "fixtures/ev_bins/sc_m1.evb": "4d4403e147b586960b0d5fa84e25dd57526ad30cf1d7744d9d543d3783d83630",
    "fixtures/ev_bins/sc_m2.evb": "dfa8ba85385b5bf33e215502d529df67532ee7aaa1f8f424a1ec43098750da6a",
    "fixtures/ev_bins/sc_m3.evb": "0948f819123e1e74cb47393d4eaed66799a25e8207e7a29e0bf9a9421200a8f9",
    "fixtures/ev_bins/sc_m4.evb": "4369a8db92964e79246b1741b9e8dbc0548dcbab1f2f00ee2cde9998aeafd906",
    "fixtures/ev_bins/sc_m5.evb": "39c3ba5cd537db97a40579d1332a5316d31cc6bae3a5e5ad1f0f657a32ad4173",
    "docs/lane_coef.json": "beac39d37c850e0420d7bc7ddfa80b26c1073e87359fa2df6aff883fc882a143",
}
HIDDEN_EVB_SHA = "0b782bf2a8ca151f21bb5794129469784c103f74193d5baa0db50550888f5f82"
HIDDEN_JSON_SHA = "43ec73ba401bc269b9185e0cc86e0e00928c218b1b224552be67ee72ffff267b"
# Sealed public matrix witnesses (contract-correct reference; independent of live env rewrite).
GOLDEN_CROSS_DIGEST = "ba09a7f5c5704e1bba737eb291236637169e4826761a0f1694375acb83f61608"
GOLDEN_REPEAT_STAMP = "096d6cd4fc64c420"
ALT_COEF_CROSS_DIGEST = "8c2af2e90a83f0f2e78829fcf7fa63d4bfc4e3370f71eed96cc329ee806bfca5"
HIDDEN_STRICT_DIGEST = "569e28512c9341e3810f15da0a721854d67ec5ceab4c5b02b6189b498087cccc"
MUTATED_SC_M1_STRICT_DIGEST = "82f88581d708869aec5b7bf9e66b11cdf2bc5a6507f0df417f8cf90b34fcb598"


@dataclass(frozen=True)
class ScenarioSpec:
    codename: str
    ev_bin: str
    band_lo: int
    band_hi: int
    combo: bool
    mag_seed: int
    dur_seed: int
    combo_depth: int
    entity_a: int
    entity_b: int


def rebuild_lab() -> None:
    subprocess.run(["bash", "/app/environment/scripts/build_lab.sh"], check=True)


def reset_settle_state(poisoned: bool = False, pulse_carry: int = 0) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"poisoned": poisoned, "pulse_carry": pulse_carry}))
    JOURNAL_PATH.write_text("")


def run_full_matrix(
    env_root: Path | None = None,
    out_path: Path | None = None,
) -> tuple[int, dict]:
    target = out_path or OUT
    target.unlink(missing_ok=True)
    env = os.environ.copy()
    if env_root is not None:
        env["MDL_ENV_ROOT"] = str(env_root)
    proc = subprocess.run(
        [MDL_LAB, "--full-matrix", "--depth", "5", "--out", str(target)],
        capture_output=True,
        text=True,
        env=env,
    )
    matrix = json.loads(target.read_text()) if target.exists() else {}
    return proc.returncode, matrix


def stage_replay_tree() -> Path:
    """Copy graded replay inputs into a writable scratch tree outside /tests."""
    scratch = Path(tempfile.mkdtemp(prefix="mdl_probe_"))
    shutil.copytree(ENV / "scenarios", scratch / "scenarios")
    shutil.copytree(ENV / "docs", scratch / "docs")
    shutil.copytree(ENV / "fixtures", scratch / "fixtures")
    return scratch


def write_manifest_slot(root: Path, codename: str, spec: ScenarioSpec, ev_bytes: bytes) -> None:
    """Install probe bytes into a staged manifest slot (never the live ENV tree)."""
    payload = {
        "combo": spec.combo,
        "codename": codename,
        "ev_bin": f"{codename}.evb",
        "band_lo": spec.band_lo,
        "band_hi": spec.band_hi,
        "mag_seed": spec.mag_seed,
        "dur_seed": spec.dur_seed,
        "combo_depth": spec.combo_depth,
        "entity_a": spec.entity_a,
        "entity_b": spec.entity_b,
    }
    (root / "scenarios" / f"{codename}.json").write_text(json.dumps(payload, indent=2) + "\n")
    (root / "fixtures" / "ev_bins" / f"{codename}.evb").write_bytes(ev_bytes)


def row_for(matrix: dict, codename: str, profile: str) -> dict:
    return next(r for r in matrix["runs"] if r["codename"] == codename and r["profile"] == profile)


def assert_public_inputs_pinned() -> None:
    """Reject agent rewrites of graded public scenario / EVB / coefficient inputs."""
    for rel, want in PUBLIC_FIXTURE_SHA256.items():
        path = ENV / rel
        assert path.exists(), f"graded public input missing: {rel}"
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        assert got == want, f"graded public input was modified: {rel}"


def assert_hidden_inputs_pinned() -> None:
    assert (
        hashlib.sha256(HIDDEN_DIR.joinpath("h7_tie_probe.evb").read_bytes()).hexdigest()
        == HIDDEN_EVB_SHA
    )
    assert (
        hashlib.sha256(HIDDEN_DIR.joinpath("h7_tie_probe.json").read_bytes()).hexdigest()
        == HIDDEN_JSON_SHA
    )


def load_coef(root: Path | None = None) -> dict:
    base = root or ENV
    return json.loads((base / "docs" / "lane_coef.json").read_text())


def load_hidden_probe_spec(slot_codename: str, slot_ev_bin: str) -> ScenarioSpec:
    """Hidden probe fields remapped onto a public matrix slot name."""
    data = json.loads(HIDDEN_DIR.joinpath("h7_tie_probe.json").read_text())
    return ScenarioSpec(
        codename=slot_codename,
        ev_bin=slot_ev_bin,
        band_lo=int(data["band_lo"]),
        band_hi=int(data["band_hi"]),
        combo=bool(data["combo"]),
        mag_seed=int(data["mag_seed"]),
        dur_seed=int(data["dur_seed"]),
        combo_depth=int(data["combo_depth"]),
        entity_a=int(data["entity_a"]),
        entity_b=int(data["entity_b"]),
    )


def load_scenario(path: Path) -> ScenarioSpec:
    data = json.loads(path.read_text())
    return ScenarioSpec(
        codename=data["codename"],
        ev_bin=data["ev_bin"],
        band_lo=int(data["band_lo"]),
        band_hi=int(data["band_hi"]),
        combo=bool(data.get("combo", False)),
        mag_seed=int(data.get("mag_seed", 0)),
        dur_seed=int(data.get("dur_seed", 0)),
        combo_depth=int(data.get("combo_depth", 4)),
        entity_a=int(data.get("entity_a", 10)),
        entity_b=int(data.get("entity_b", 20)),
    )


def parse_ev_bytes(raw: bytes) -> tuple[bytes, int, int, int, int, int, tuple[int, ...]]:
    if len(raw) < 12 or raw[:4] != b"EVB\x01":
        raise ValueError("invalid ev bin header")
    mag_seed = raw[4]
    dur_seed = raw[5]
    entity_a = raw[6]
    entity_b = raw[7]
    combo_depth = raw[8]
    payload = raw[12:]
    activations = tuple(payload[i] % 16 for i in range(min(combo_depth, len(payload))))
    return payload, mag_seed, dur_seed, entity_a, entity_b, combo_depth, activations


def stack_merge_ref(mag: int, dur: int, stack_id: int, mag_d: int, dur_d: int, lane: str, coef: dict) -> tuple[int, int, int]:
    new_mag = mag + mag_d
    new_dur = dur + dur_d
    weight = coef["primary"] if lane == "primary" else coef["secondary"]
    return new_mag, new_dur, (stack_id ^ mag_d) + new_dur + weight


def rebuild_canonical_ref(payload: bytes, mag_seed: int, dur_seed: int, coef: dict) -> bytes:
    new_mag, new_dur, new_id = stack_merge_ref(
        mag_seed,
        dur_seed,
        mag_seed ^ dur_seed,
        mag_seed % 7 + 1,
        dur_seed % 5 + 1,
        "primary",
        coef,
    )
    return bytes([new_mag % 256, new_dur % 256, new_id % 256]) + payload


def enumerate_combos(activations: tuple[int, ...], depth_limit: int) -> list[tuple[int, ...]]:
    if not activations:
        return [()]
    combos: list[tuple[int, ...]] = [()]
    frontier: list[tuple[int, ...]] = [()]
    while frontier and len(combos) < depth_limit + 1:
        current = frontier.pop(0)
        if len(current) >= depth_limit:
            continue
        for item in activations[:3]:
            nxt = current + (item,)
            combos.append(nxt)
            frontier.append(nxt)
    return combos[: depth_limit + 1]


def plan_pulse_ref(tick: int, period: int, pending: int, profile: str, iframe_active: bool, overlap: int) -> tuple[bool, int, int]:
    on_boundary = tick > 0 and tick % period == 0
    if not on_boundary:
        return False, pending, 0
    if iframe_active and overlap > 0:
        return False, pending + period, 0
    if profile == "loose_tick" and pending > period:
        return False, pending, 0
    return True, 0, pending + 1


def apply_settle_ref(hp_a: int, hp_b: int, entity_a: int, entity_b: int) -> int:
    lethal_a = hp_a <= 0
    lethal_b = hp_b <= 0
    if lethal_a and lethal_b:
        return min(entity_a, entity_b)
    if lethal_a and not lethal_b:
        return entity_a
    if lethal_b and not lethal_a:
        return entity_b
    return -1


def depth_for(spec: ScenarioSpec, depth: int = 5, root: Path | None = None) -> int:
    base = root or ENV
    sweep = load_scenario(base / "scenarios" / "sweep_m0.json")
    return depth if spec.combo or sweep.combo else min(depth, 3)


def simulate_row_ref(
    spec: ScenarioSpec,
    profile: str,
    combo: tuple[int, ...],
    depth_limit: int,
    state: dict,
    coef: dict,
    ev_dir: Path,
) -> tuple[bytes, int, int, int, list[dict], dict]:
    raw = (ev_dir / spec.ev_bin).read_bytes()
    payload, mag_seed, dur_seed, entity_a, entity_b, _, _ = parse_ev_bytes(raw)
    canonical = rebuild_canonical_ref(payload, mag_seed, dur_seed, coef)

    period = max(2, dur_seed % 5 + 2)
    fire_now, deferred, pulse_count = plan_pulse_ref(
        mag_seed,
        period,
        len(combo),
        profile,
        bool(dur_seed % 2),
        dur_seed % 4,
    )

    violations: list[dict] = []
    if profile == "loose_tick" and bool(dur_seed % 2) and fire_now:
        violations.append(
            {
                "codename": spec.codename,
                "profile": profile,
                "combo_len": len(combo),
                "reason_code": "pulse_overlap",
            }
        )

    penalty = 0 if deferred else pulse_count
    hp_a = max(0, 100 - sum(combo) - penalty)
    hp_b = max(0, 100 - mag_seed - dur_seed - len(combo))
    winner = apply_settle_ref(hp_a, hp_b, entity_a, entity_b)
    settled = winner >= 0
    if hp_a <= 0 and hp_b <= 0 and settled and winner != min(entity_a, entity_b):
        violations.append(
            {
                "codename": spec.codename,
                "profile": profile,
                "combo_len": len(combo),
                "reason_code": "tie_order",
            }
        )

    if state.get("poisoned"):
        violations.append(
            {
                "codename": spec.codename,
                "profile": profile,
                "combo_len": len(combo),
                "reason_code": "state_poison",
            }
        )

    carry = int(state.get("pulse_carry", 0))
    residue = (carry + pulse_count + mag_seed) % 256
    state = {"poisoned": bool(state.get("poisoned", False)), "pulse_carry": residue}

    slot_lo = min(combo) if combo else spec.band_lo
    slot_hi = max(combo) if combo else spec.band_hi
    entropy = (sum(combo) + residue + mag_seed + dur_seed) % 256
    band_lo = max(spec.band_lo, min(slot_lo, entropy))
    band_hi = min(spec.band_hi, max(slot_hi, entropy + 1, band_lo + 1))
    row_count = len(combo) + pulse_count + 1
    material = canonical + bytes([residue]) + bytes(combo)
    return material, band_lo, band_hi, row_count, violations, state


def reference_manifest_row(
    codename: str,
    profile: str,
    depth: int = 5,
    ev_dir: Path | None = None,
    coef: dict | None = None,
    spec: ScenarioSpec | None = None,
    env_root: Path | None = None,
) -> dict:
    """Sealed contract-correct row — does not import agent modules."""
    base = env_root or ENV
    coef = coef if coef is not None else load_coef(base)
    spec = spec if spec is not None else load_scenario(base / "scenarios" / f"{codename}.json")
    depth_limit = depth_for(spec, depth, root=base)
    root = ev_dir or (base / "fixtures" / "ev_bins")
    state = {"poisoned": False, "pulse_carry": 0}

    raw = (root / spec.ev_bin).read_bytes()
    _, mag_seed, dur_seed, _, _, _, activations = parse_ev_bytes(raw)
    combos = enumerate_combos(activations, depth_limit)

    digests: list[str] = []
    violations: list[dict] = []
    band_lo = spec.band_lo
    band_hi = spec.band_hi
    row_count = 0
    for combo in combos:
        material, lo, hi, rows, combo_violations, state = simulate_row_ref(
            spec, profile, combo, depth_limit, state, coef, root
        )
        violations.extend(combo_violations)
        digests.append(hashlib.sha256(material).hexdigest())
        band_lo = max(band_lo, lo)
        band_hi = min(band_hi, hi)
        row_count = max(row_count, rows)

    return {
        "codename": codename,
        "profile": profile,
        "digest_hex": hashlib.sha256("".join(digests).encode()).hexdigest(),
        "violation_rows": len(violations),
        "violations": violations,
        "band_lo": band_lo,
        "band_hi": band_hi,
        "row_count": row_count,
        "depth_limit": depth_limit,
        "event_bytes_len": len(rebuild_canonical_ref(raw[12:], mag_seed, dur_seed, coef)),
    }


def reference_repeat_stamp(runs: list[dict]) -> str:
    payload = deepcopy(runs)
    for row in payload:
        row.setdefault("violations", [])
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def reference_cross_digest(runs: list[dict]) -> str:
    return hashlib.sha256("".join(r["digest_hex"] for r in runs).encode()).hexdigest()


def build_reference_matrix(
    depth: int = 5,
    coef: dict | None = None,
    env_root: Path | None = None,
) -> dict:
    runs: list[dict] = []
    for codename in MANIFESTS:
        for profile in PROFILES:
            runs.append(
                reference_manifest_row(
                    codename, profile, depth, coef=coef, env_root=env_root
                )
            )
    return {
        "matrix_tag": "cmb_v2",
        "depth_limit": runs[0]["depth_limit"] if runs else depth,
        "runs": [{k: v for k, v in row.items() if k != "violations"} for row in runs],
        "violation_total": sum(r["violation_rows"] for r in runs),
        "cross_digest": reference_cross_digest(runs),
        "repeat_stamp": reference_repeat_stamp(runs),
    }


@pytest.fixture(scope="module")
def matrix() -> dict:
    assert_public_inputs_pinned()
    rebuild_lab()
    reset_settle_state()
    code, body = run_full_matrix()
    assert code == 0, f"mdl_lab must exit cleanly after repair\n{body}"
    return body


@pytest.fixture(scope="module")
def expected() -> dict:
    """Reference matrix only after public inputs match baked pins."""
    assert_public_inputs_pinned()
    body = build_reference_matrix()
    assert body["cross_digest"] == GOLDEN_CROSS_DIGEST
    assert body["repeat_stamp"] == GOLDEN_REPEAT_STAMP
    return body


def test_matrix_pipeline_exits_clean(matrix: dict, expected: dict) -> None:
    """Full matrix run completes with contract schema and zero violations."""
    assert matrix["matrix_tag"] == "cmb_v2"
    assert matrix["violation_total"] == 0 == expected["violation_total"]
    seen = {(row["codename"], row["profile"]) for row in matrix["runs"]}
    assert seen == set(RUN_ORDER)


def test_run_order_matches_public_contract(matrix: dict) -> None:
    """Matrix rows follow manifest-major, profile-minor ordering."""
    got = [(r["codename"], r["profile"]) for r in matrix["runs"]]
    assert got == RUN_ORDER


def test_cross_digest_run_order_recompute(matrix: dict, expected: dict) -> None:
    """cross_digest matches sealed run-order concatenation."""
    assert matrix["cross_digest"] == expected["cross_digest"]
    assert matrix["cross_digest"] == reference_cross_digest(matrix["runs"])


def test_cross_digest_rejects_sorted_trap(matrix: dict) -> None:
    """Lexicographically sorting per-run digests must not reproduce cross_digest."""
    sorted_trap = hashlib.sha256(
        "".join(sorted(r["digest_hex"] for r in matrix["runs"])).encode()
    ).hexdigest()
    assert matrix["cross_digest"] != sorted_trap


def test_repeat_stamp_pre_strip_contract(matrix: dict, expected: dict) -> None:
    """repeat_stamp hashes pre-output rows that still carry violations lists."""
    assert matrix["repeat_stamp"] == expected["repeat_stamp"]


def test_per_manifest_digest_matches_sealed_reference(matrix: dict, expected: dict) -> None:
    """Each run digest matches independent contract recomputation."""
    for row in expected["runs"]:
        actual = row_for(matrix, row["codename"], row["profile"])
        assert actual["digest_hex"] == row["digest_hex"]
        assert actual["violation_rows"] == 0
        assert actual["band_lo"] == row["band_lo"]
        assert actual["band_hi"] == row["band_hi"]
        assert actual["row_count"] == row["row_count"]
        assert actual["event_bytes_len"] == row["event_bytes_len"]


def test_combo_digest_rejects_sorted_chain(matrix: dict) -> None:
    """Per-manifest digest must not use lexicographically sorted combo digests."""
    ref = reference_manifest_row("sc_m5", "strict_tick")
    sorted_trap = None
    spec = load_scenario(ENV / "scenarios" / "sc_m5.json")
    depth_limit = depth_for(spec)
    coef = load_coef()
    state = {"poisoned": False, "pulse_carry": 0}
    raw = (EV_DIR / spec.ev_bin).read_bytes()
    _, _, _, _, _, _, activations = parse_ev_bytes(raw)
    digests = []
    for combo in enumerate_combos(activations, depth_limit):
        material, *_rest, state = simulate_row_ref(
            spec, "strict_tick", combo, depth_limit, state, coef, EV_DIR
        )
        digests.append(hashlib.sha256(material).hexdigest())
    sorted_trap = hashlib.sha256("".join(sorted(digests)).encode()).hexdigest()
    assert row_for(matrix, "sc_m5", "strict_tick")["digest_hex"] == ref["digest_hex"]
    assert ref["digest_hex"] != sorted_trap


def test_carry_isolated_per_matrix_row(matrix: dict) -> None:
    """Later manifests match isolated recomputation with carry reset."""
    isolated = reference_manifest_row("sc_m4", "loose_tick")
    assert row_for(matrix, "sc_m4", "loose_tick")["digest_hex"] == isolated["digest_hex"]


def test_event_bytes_len_stable_across_profiles(matrix: dict) -> None:
    """Canonical byte length is profile-invariant for each manifest."""
    for codename in MANIFESTS:
        strict = row_for(matrix, codename, "strict_tick")
        loose = row_for(matrix, codename, "loose_tick")
        assert strict["event_bytes_len"] == loose["event_bytes_len"]


def test_event_bytes_len_from_evb_payload(matrix: dict) -> None:
    """event_bytes_len equals ev bin payload size plus three header bytes."""
    for codename in MANIFESTS:
        spec = json.loads((ENV / "scenarios" / f"{codename}.json").read_text())
        payload_len = len((EV_DIR / spec["ev_bin"]).read_bytes()) - 12
        for profile in PROFILES:
            row = row_for(matrix, codename, profile)
            assert row["event_bytes_len"] == payload_len + 3


def test_band_window_within_manifest(matrix: dict) -> None:
    """Graded band windows stay inside each manifest envelope."""
    for codename in MANIFESTS:
        spec = json.loads((ENV / "scenarios" / f"{codename}.json").read_text())
        for profile in PROFILES:
            row = row_for(matrix, codename, profile)
            assert spec["band_lo"] <= row["band_lo"] <= row["band_hi"] <= spec["band_hi"]


def test_combo_tie_manifests_zero_violations(matrix: dict) -> None:
    """Combo manifests with inverted action-order still settle without tie violations."""
    for codename in ("sc_m3", "sc_m4", "sc_m5"):
        for profile in PROFILES:
            assert row_for(matrix, codename, profile)["violation_rows"] == 0


def test_interim_stub_not_graded_digest(matrix: dict) -> None:
    """Interim tally columns are not accepted as matrix digests."""
    stub = json.loads(STUB.read_text())
    digests = {r["digest_hex"] for r in matrix["runs"]}
    assert stub["col_a"] == stub["col_b"]
    assert stub["col_a"] not in digests


def test_widen_without_restore_fails() -> None:
    """Destructive cleanup without documented restore fails the graded matrix."""
    rebuild_lab()
    reset_settle_state()
    subprocess.run(["bash", "/app/environment/migrations/cln7.sh"], check=True)
    code, body = run_full_matrix()
    assert code != 0 or body.get("violation_total", 1) > 0


def test_restore_copies_full_seed_and_clears_journal() -> None:
    """--restore must replace settle fields from the seed and clear the journal."""
    rebuild_lab()
    reset_settle_state()
    JOURNAL_PATH.write_text('{"codename":"x","profile":"strict_tick","residue":99}\n')
    subprocess.run(["bash", "/app/environment/migrations/cln7.sh"], check=True)
    subprocess.run(
        [
            "bash",
            "/app/environment/migrations/cln7.sh",
            "--restore",
            "/app/environment/fixtures/seed_store/arena_seed.bin",
        ],
        check=True,
    )
    state = json.loads(STATE_PATH.read_text())
    assert state["poisoned"] is False
    assert state["pulse_carry"] == 0
    assert JOURNAL_PATH.read_text() == ""


def test_rerun_after_restore_succeeds(expected: dict) -> None:
    """Documented recovery path returns a clean matrix matching sealed witnesses."""
    rebuild_lab()
    reset_settle_state()
    subprocess.run(["bash", "/app/environment/migrations/cln7.sh"], check=True)
    subprocess.run(
        [
            "bash",
            "/app/environment/migrations/cln7.sh",
            "--restore",
            "/app/environment/fixtures/seed_store/arena_seed.bin",
        ],
        check=True,
    )
    before = {name: (EV_DIR / f"{name}.evb").read_bytes() for name in MANIFESTS}
    code, body = run_full_matrix()
    assert code == 0
    assert body["violation_total"] == 0
    assert body["repeat_stamp"] == expected["repeat_stamp"]
    after = {name: (EV_DIR / f"{name}.evb").read_bytes() for name in MANIFESTS}
    assert before == after


def test_matrix_rerun_idempotent(expected: dict) -> None:
    """Back-to-back matrix runs emit identical stamps after state reset."""
    rebuild_lab()
    reset_settle_state()
    code_a, first = run_full_matrix()
    reset_settle_state()
    code_b, second = run_full_matrix()
    assert code_a == code_b == 0
    assert first["cross_digest"] == second["cross_digest"] == expected["cross_digest"]
    assert first["repeat_stamp"] == second["repeat_stamp"] == expected["repeat_stamp"]


def test_second_process_after_restore_matches(expected: dict) -> None:
    """Fresh process after restore reproduces sealed repeat_stamp."""
    rebuild_lab()
    reset_settle_state()
    subprocess.run(["bash", "/app/environment/migrations/cln7.sh"], check=True)
    subprocess.run(
        [
            "bash",
            "/app/environment/migrations/cln7.sh",
            "--restore",
            "/app/environment/fixtures/seed_store/arena_seed.bin",
        ],
        check=True,
    )
    code, body = run_full_matrix()
    assert code == 0
    assert body["repeat_stamp"] == expected["repeat_stamp"]


def test_public_inputs_remain_pinned(matrix: dict) -> None:
    """Graded public scenarios, EVBs, and lane coefficients stay at baked digests."""
    assert_public_inputs_pinned()
    assert matrix["cross_digest"] == GOLDEN_CROSS_DIGEST


def test_hidden_fixture_checksum_stable() -> None:
    """Hidden verifier fixture bytes remain pinned for independent probes."""
    assert_hidden_inputs_pinned()


def test_binary_matches_hidden_probe_digest(matrix: dict) -> None:
    """Submitted binary must match sealed digest on an independent hidden probe."""
    assert_hidden_inputs_pinned()
    slot = "sc_m5"
    base = row_for(matrix, slot, "strict_tick")["digest_hex"]
    assert base != HIDDEN_STRICT_DIGEST
    probe = load_hidden_probe_spec(slot, f"{slot}.evb")
    scratch = stage_replay_tree()
    out_path = Path(tempfile.mkdtemp(prefix="mdl_out_")) / "cmb_out.json"
    try:
        write_manifest_slot(
            scratch, slot, probe, HIDDEN_DIR.joinpath("h7_tie_probe.evb").read_bytes()
        )
        reset_settle_state()
        code, body = run_full_matrix(env_root=scratch, out_path=out_path)
        assert code == 0
        assert row_for(body, slot, "strict_tick")["digest_hex"] == HIDDEN_STRICT_DIGEST
        assert row_for(body, slot, "loose_tick")["digest_hex"] == HIDDEN_STRICT_DIGEST
        ref = reference_manifest_row(slot, "strict_tick", env_root=scratch, spec=probe)
        assert ref["digest_hex"] == HIDDEN_STRICT_DIGEST
        assert ref["violation_rows"] == 0
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        shutil.rmtree(out_path.parent, ignore_errors=True)
        reset_settle_state()
        assert_public_inputs_pinned()


def test_binary_matches_mutated_mag_seed_digest(matrix: dict) -> None:
    """Submitted binary must track an independent mag_seed mutation (anti hard-code)."""
    assert_public_inputs_pinned()
    base = row_for(matrix, "sc_m1", "strict_tick")["digest_hex"]
    scratch = stage_replay_tree()
    out_path = Path(tempfile.mkdtemp(prefix="mdl_out_")) / "cmb_out.json"
    try:
        ev_path = scratch / "fixtures" / "ev_bins" / "sc_m1.evb"
        raw = bytearray(ev_path.read_bytes())
        raw[4] = (raw[4] + 1) % 256
        ev_path.write_bytes(raw)
        reset_settle_state()
        code, body = run_full_matrix(env_root=scratch, out_path=out_path)
        assert code == 0
        shifted = row_for(body, "sc_m1", "strict_tick")["digest_hex"]
        assert shifted == MUTATED_SC_M1_STRICT_DIGEST
        assert shifted != base
        spec = load_scenario(scratch / "scenarios" / "sc_m1.json")
        ref = reference_manifest_row("sc_m1", "strict_tick", env_root=scratch, spec=spec)
        assert ref["digest_hex"] == MUTATED_SC_M1_STRICT_DIGEST
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        shutil.rmtree(out_path.parent, ignore_errors=True)
        reset_settle_state()
        assert_public_inputs_pinned()


def test_sc_m5_combo_row_count_wider(matrix: dict) -> None:
    """Combo-depth manifest reports wider row_count than non-combo manifests."""
    m5 = row_for(matrix, "sc_m5", "strict_tick")["row_count"]
    others = [row_for(matrix, c, "strict_tick")["row_count"] for c in ("sc_m1", "sc_m2", "sc_m3", "sc_m4")]
    assert m5 > max(others)


def test_poison_state_before_restore() -> None:
    """Destructive cleanup poisons settle state until a full seed restore."""
    rebuild_lab()
    reset_settle_state()
    subprocess.run(["bash", "/app/environment/migrations/cln7.sh"], check=True)
    state = json.loads(STATE_PATH.read_text())
    assert state["poisoned"] is True
    assert state["pulse_carry"] == 255


def test_strict_tick_digest_unique_per_manifest(matrix: dict) -> None:
    """Each manifest contributes a distinct strict_tick digest to the matrix."""
    digests = [row_for(matrix, codename, "strict_tick")["digest_hex"] for codename in MANIFESTS]
    assert len(set(digests)) == len(MANIFESTS)


def test_lane_coef_binding_shifts_digest(matrix: dict) -> None:
    """Lane coefficient binding must match sealed recomputation (not a dummy delta)."""
    assert_public_inputs_pinned()
    coef = load_coef()
    assert coef["primary"] == 3 and coef["secondary"] == 5
    alt = dict(coef)
    alt["primary"] = coef["primary"] + 1
    scratch = stage_replay_tree()
    out_path = Path(tempfile.mkdtemp(prefix="mdl_out_")) / "cmb_out.json"
    try:
        (scratch / "docs" / "lane_coef.json").write_text(json.dumps(alt))
        reset_settle_state()
        code, body = run_full_matrix(env_root=scratch, out_path=out_path)
        assert code == 0
        expected_alt = build_reference_matrix(coef=alt, env_root=scratch)
        assert body["cross_digest"] == expected_alt["cross_digest"] == ALT_COEF_CROSS_DIGEST
        assert body["cross_digest"] != matrix["cross_digest"]
        assert body["repeat_stamp"] == expected_alt["repeat_stamp"]
        for row in expected_alt["runs"]:
            actual = row_for(body, row["codename"], row["profile"])
            assert actual["digest_hex"] == row["digest_hex"]
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
        shutil.rmtree(out_path.parent, ignore_errors=True)
        reset_settle_state()
        assert_public_inputs_pinned()


def test_journal_must_not_reseeds_carry_after_restore(expected: dict) -> None:
    """Uncleared journal residue must not re-seed carry after a correct restore."""
    rebuild_lab()
    reset_settle_state()
    subprocess.run(["bash", "/app/environment/migrations/cln7.sh"], check=True)
    subprocess.run(
        [
            "bash",
            "/app/environment/migrations/cln7.sh",
            "--restore",
            "/app/environment/fixtures/seed_store/arena_seed.bin",
        ],
        check=True,
    )
    # Inject a stale journal line after restore (LoadState must ignore it).
    JOURNAL_PATH.write_text('{"codename":"sc_m1","profile":"strict_tick","residue":77}\n')
    code, body = run_full_matrix()
    assert code == 0
    assert body["repeat_stamp"] == expected["repeat_stamp"]

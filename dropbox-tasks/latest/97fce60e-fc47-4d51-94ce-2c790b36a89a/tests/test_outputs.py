"""Verification for loot distribution fairness validator."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPORT_PATH = Path("/app/out/fairness_report.json")
REPORT_FIRST = Path("/logs/verifier/report_first.json")
VERIFIER_DIR = Path("/logs/verifier")
VAULT_DIR = Path("/app/dropvault")
CATALOG_PATH = VAULT_DIR / "catalog.json"
APP_DIR = Path("/app")
SESSION_COUNT = 20

FINDING_KINDS = frozenset(
    {
        "RNG_MISMATCH",
        "PITY_VIOLATION",
        "POOL_MISMATCH",
        "TIER_MISMATCH",
        "DUPLICATE_UNIQUE",
        "COOLDOWN_BREACH",
        "CHI_SQUARE_HIGH",
        "GINI_UNFAIR",
        "STREAK_SKEW",
        "DUPLICATE_SEQ",
        "VARIANCE_SPIKE",
    }
)
FINDING_ID_RE = re.compile(r"^[^:]+::[^:]+::[^:]+::\d{4}$")
IMMUTABLE_SHA256: dict[str, str] = {}

MOD = 2**31
A_LCG, C_LCG = 1103515245, 12345
RNG_EPS = 1e-9
CHI_THRESHOLD = 6.635
GINI_THRESHOLD = 0.55
VARIANCE_THRESHOLD = 0.08


def _round4(value: float) -> float:
    rounded = round(value, 4)
    if rounded == int(rounded):
        return int(rounded)  # type: ignore[return-value]
    return rounded


def _next_roll(state: int) -> tuple[float, int]:
    rv = ((state >> 16) & 0x7FFF) / 32767.0
    state = (A_LCG * state + C_LCG) % MOD
    return rv, state


def _pool_sorted(pool: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(pool, key=lambda x: x["item_id"])


def _select_item(roll_value: float, pool: list[dict[str, Any]], pity_tier: str | None) -> dict[str, Any]:
    ps = _pool_sorted(pool)
    if pity_tier:
        pity = [p for p in ps if p["tier"] == pity_tier]
        if pity:
            return pity[0]
    total = sum(int(p["weight"]) for p in ps)
    if total <= 0:
        return ps[0]
    target = roll_value * total
    cum = 0
    for p in ps:
        cum += int(p["weight"])
        if target <= cum:
            return p
    return ps[-1]


def _tier_weights(pool: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for p in pool:
        out[p["tier"]] = out.get(p["tier"], 0) + int(p["weight"])
    return out


def _gini(counts: list[int]) -> float:
    if not counts:
        return 0.0
    vals = sorted(counts)
    n = len(vals)
    total = sum(vals)
    if total == 0:
        return 0.0
    num = 0
    for i, v in enumerate(vals, start=1):
        num += i * v
    return (2 * num) / (n * total) - (n + 1) / n


def _population_variance(values: list[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def _finding_id(session_id: str, player_id: str, kind: str, seq: int) -> str:
    return f"{session_id}::{player_id}::{kind}::{seq:04d}"


def analyze_session(session: dict[str, Any]) -> dict[str, Any]:
    """Independent fairness engine for loot roll sessions."""
    sid = session["session_id"]
    pity_threshold = int(session["pity_threshold"])
    pity_tier = session["pity_tier"]
    pool = session["loot_pool"]
    pool_map = {p["item_id"]: p for p in pool}
    tw = _tier_weights(pool)
    total_weight = sum(tw.values())

    findings: list[dict[str, Any]] = []
    tier_counts: dict[str, int] = {}
    player_rolls: dict[str, int] = {}
    epic_by_player: dict[str, int] = {}
    natural_epic_by_player: dict[str, int] = {}
    unique_seen: dict[tuple[str, str], int] = {}
    last_item_seq: dict[tuple[str, str], int] = {}
    seen_seq: set[int] = set()
    recent_values: list[float] = []

    state = int(session["rng_seed"])
    since_pity = 0
    streak_tier = ""
    streak_len = 0

    def add_finding(player_id: str, kind: str, detail: str, seq: int) -> None:
        findings.append(
            {
                "finding_id": _finding_id(sid, player_id, kind, seq),
                "player_id": player_id,
                "kind": kind,
                "detail": detail,
                "seq": seq,
            }
        )

    rolls = sorted(session["rolls"], key=lambda r: r["seq"])
    for roll in rolls:
        seq = int(roll["seq"])
        player = roll["player_id"]
        if seq in seen_seq:
            add_finding(player, "DUPLICATE_SEQ", str(seq), seq)
            continue
        seen_seq.add(seq)

        expected_rv, state = _next_roll(state)
        logged_rv = float(roll["roll_value"])
        if abs(logged_rv - expected_rv) > RNG_EPS:
            add_finding(player, "RNG_MISMATCH", f"{logged_rv:.12f}", seq)

        pity_active = since_pity >= pity_threshold
        pity_arg = pity_tier if pity_active else None
        expected_item = _select_item(expected_rv, pool, pity_arg)

        if pity_active and roll["item_id"] != expected_item["item_id"]:
            add_finding(player, "PITY_VIOLATION", expected_item["item_id"], seq)

        if roll["item_id"] not in pool_map:
            add_finding(player, "POOL_MISMATCH", roll["item_id"], seq)
        else:
            if pool_map[roll["item_id"]]["tier"] != roll["tier"]:
                add_finding(player, "TIER_MISMATCH", roll["tier"], seq)
            item_meta = pool_map[roll["item_id"]]
            key = (player, roll["item_id"])
            if item_meta["unique"]:
                if key in unique_seen:
                    add_finding(player, "DUPLICATE_UNIQUE", roll["item_id"], seq)
                else:
                    unique_seen[key] = seq
            cd = int(item_meta["cooldown"])
            if cd > 0 and key in last_item_seq and seq - last_item_seq[key] <= cd:
                add_finding(player, "COOLDOWN_BREACH", roll["item_id"], seq)
            last_item_seq[key] = seq

        if roll["tier"] == streak_tier:
            streak_len += 1
        else:
            streak_tier = roll["tier"]
            streak_len = 1
        if streak_len == 6:
            add_finding(player, "STREAK_SKEW", roll["tier"], seq)

        recent_values.append(logged_rv)
        if len(recent_values) > 8:
            recent_values.pop(0)
        if len(recent_values) == 8:
            var = _population_variance(recent_values)
            if var > VARIANCE_THRESHOLD:
                add_finding(player, "VARIANCE_SPIKE", f"{_round4(var):.4f}", seq)

        tier_counts[roll["tier"]] = tier_counts.get(roll["tier"], 0) + 1
        player_rolls[player] = player_rolls.get(player, 0) + 1
        if roll["tier"] == pity_tier:
            epic_by_player[player] = epic_by_player.get(player, 0) + 1
            if not pity_active:
                natural_epic_by_player[player] = natural_epic_by_player.get(player, 0) + 1
        if roll["tier"] == pity_tier and not pity_active:
            since_pity = 0
        else:
            since_pity += 1

    n_rolls = len(rolls)
    tier_stats: list[dict[str, Any]] = []
    for tier in sorted(tw):
        observed = tier_counts.get(tier, 0)
        expected = (tw[tier] / total_weight) * n_rolls if total_weight else 0.0
        chi = ((observed - expected) ** 2 / expected) if expected > 0 else 0.0
        tier_stats.append(
            {
                "tier": tier,
                "observed": observed,
                "expected": _round4(expected),
                "chi_square": _round4(chi),
            }
        )
        if n_rolls >= 30 and expected >= 5 and chi > CHI_THRESHOLD:
            add_finding(sorted(player_rolls)[0], "CHI_SQUARE_HIGH", tier, rolls[-1]["seq"])

    all_players = sorted(player_rolls)
    natural_counts = [natural_epic_by_player.get(p, 0) for p in all_players]
    gini = _gini(natural_counts)
    total_natural = sum(natural_counts)
    if total_natural >= 5 and len(all_players) >= 2 and gini > GINI_THRESHOLD:
        add_finding(all_players[0], "GINI_UNFAIR", f"{_round4(gini):.4f}", rolls[-1]["seq"] if rolls else 0)

    players = [
        {
            "player_id": pid,
            "epic_drops": epic_by_player.get(pid, 0),
            "total_rolls": player_rolls[pid],
        }
        for pid in all_players
    ]

    findings.sort(key=lambda f: f["finding_id"])
    return {
        "session_id": sid,
        "status": "FAIR" if not findings else "BIASED",
        "gini_coefficient": _round4(gini),
        "tier_stats": tier_stats,
        "players": players,
        "findings": findings,
    }


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_make(target: str, log_name: str, *, fail_hard: bool = True) -> bool:
    proc = subprocess.run(["make", target], cwd=APP_DIR, capture_output=True, text=True)
    (VERIFIER_DIR / log_name).write_text(proc.stdout + proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        if fail_hard:
            pytest.fail(f"make {target} failed; see /logs/verifier/{log_name}")
        return False
    return True


@pytest.fixture(scope="session", autouse=True)
def _verifier_grading_setup() -> None:
    """Rerun make run twice to verify determinism."""
    try:
        VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_FIRST.unlink(missing_ok=True)
        if not _run_make("build", "build.log", fail_hard=False):
            return
        REPORT_PATH.unlink(missing_ok=True)
        if not _run_make("run", "run.log", fail_hard=False):
            return
        if REPORT_PATH.is_file():
            shutil.copy(REPORT_PATH, REPORT_FIRST)
            _run_make("run", "run2.log", fail_hard=False)
    except Exception as exc:  # noqa: BLE001
        (VERIFIER_DIR / "grading_setup_error.log").write_text(str(exc), encoding="utf-8")


@pytest.fixture(scope="session", autouse=True)
def _capture_immutable_hashes(_verifier_grading_setup: None) -> None:
    if IMMUTABLE_SHA256:
        return
    for rel in ("Makefile", "go.mod"):
        IMMUTABLE_SHA256[rel] = _sha256_file(APP_DIR / rel)
    for path in sorted(VAULT_DIR.rglob("*")):
        if path.is_file():
            IMMUTABLE_SHA256[path.relative_to(APP_DIR).as_posix()] = _sha256_file(path)


def _normalize_numeric(value: int | float) -> int | float:
    if isinstance(value, float) and value == int(value):
        return int(value)
    return value


def _normalize_session_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": row["session_id"],
        "status": row["status"],
        "gini_coefficient": _normalize_numeric(row["gini_coefficient"]),
        "tier_stats": [
            {
                "tier": stat["tier"],
                "observed": stat["observed"],
                "expected": _normalize_numeric(stat["expected"]),
                "chi_square": _normalize_numeric(stat["chi_square"]),
            }
            for stat in row["tier_stats"]
        ],
        "players": [
            {
                "player_id": player["player_id"],
                "epic_drops": player["epic_drops"],
                "total_rolls": player["total_rolls"],
            }
            for player in row["players"]
        ],
        "findings": sorted(
            row["findings"],
            key=lambda finding: (
                finding["finding_id"],
                finding["detail"],
                finding["kind"],
                finding["player_id"],
                finding["seq"],
            ),
        ),
    }


def _session_row(report: dict[str, Any], session_id: str) -> dict[str, Any]:
    for row in report["sessions"]:
        if row["session_id"] == session_id:
            return row
    raise KeyError(session_id)


def _expected_session_row(session_id: str) -> dict[str, Any]:
    session = json.loads((VAULT_DIR / f"{session_id}.json").read_text(encoding="utf-8"))
    return _normalize_session_row(analyze_session(session))


def _assert_session_matches(report: dict[str, Any], session_id: str) -> None:
    expected = _expected_session_row(session_id)
    actual = _normalize_session_row(_session_row(report, session_id))
    assert actual == expected, session_id


@pytest.fixture(scope="module")
def report() -> dict[str, Any]:
    assert REPORT_PATH.is_file(), f"missing {REPORT_PATH}"
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


def test_rng_mismatch_uses_expected_rv(report: dict[str, Any]) -> None:
    """RNG_MISMATCH detail and downstream pity/selection must use LCG expected_rv (session_02)."""
    _assert_session_matches(report, "session_02")


def test_pity_active_at_inclusive_threshold(report: dict[str, Any]) -> None:
    """Pity must fire when rolls_since_reset reaches pity_threshold (session_03)."""
    _assert_session_matches(report, "session_03")


def test_session_01_finding_completeness(report: dict[str, Any]) -> None:
    """Session_01 baseline replay and selection must match reference."""
    _assert_session_matches(report, "session_01")


def test_session_07_finding_completeness(report: dict[str, Any]) -> None:
    """Natural epic gini session must match reference (session_07)."""
    _assert_session_matches(report, "session_07")


def test_duplicate_unique_bob_relic(report: dict[str, Any]) -> None:
    """Second relic to bob must raise DUPLICATE_UNIQUE (session_04)."""
    row = _session_row(report, "session_04")
    expected = _expected_session_row("session_04")
    bob_dups = [f for f in row["findings"] if f["kind"] == "DUPLICATE_UNIQUE" and f["player_id"] == "bob"]
    exp_bob = [f for f in expected["findings"] if f["kind"] == "DUPLICATE_UNIQUE" and f["player_id"] == "bob"]
    assert bob_dups == exp_bob


def test_cooldown_breach_uses_seq_gap(report: dict[str, Any]) -> None:
    """Gem drops within cooldown seq gap must raise COOLDOWN_BREACH (session_05)."""
    _assert_session_matches(report, "session_05")


def test_chi_square_and_tier_stats(report: dict[str, Any]) -> None:
    """Tier stats and CHI_SQUARE_HIGH must match reference (session_06)."""
    row = _session_row(report, "session_06")
    expected = _expected_session_row("session_06")
    assert row["tier_stats"] == expected["tier_stats"]
    chi = [f for f in row["findings"] if f["kind"] == "CHI_SQUARE_HIGH"]
    exp_chi = [f for f in expected["findings"] if f["kind"] == "CHI_SQUARE_HIGH"]
    assert chi == exp_chi
    if chi:
        assert chi[0]["player_id"] == "d1"
        assert chi[0]["seq"] > 0


def test_gini_unfair_finding_attribution(report: dict[str, Any]) -> None:
    """GINI_UNFAIR must anchor to alphabetically first player, not last replay player (session_07)."""
    row = _session_row(report, "session_07")
    expected = _expected_session_row("session_07")
    gini = next(f for f in row["findings"] if f["kind"] == "GINI_UNFAIR")
    exp = next(f for f in expected["findings"] if f["kind"] == "GINI_UNFAIR")
    assert gini == exp
    assert gini["player_id"] == "loser1"


def test_gini_unfair_player_totals(report: dict[str, Any]) -> None:
    """Natural epic gini, player total_rolls, and GINI_UNFAIR must match (session_07)."""
    row = _session_row(report, "session_07")
    expected = _expected_session_row("session_07")
    assert row["gini_coefficient"] == expected["gini_coefficient"]
    assert row["players"] == expected["players"]
    gini = next(f for f in row["findings"] if f["kind"] == "GINI_UNFAIR")
    assert gini == next(f for f in expected["findings"] if f["kind"] == "GINI_UNFAIR")


def test_streak_skew_fires_once_at_six(report: dict[str, Any]) -> None:
    """Exactly one STREAK_SKEW at seq 6 (session_11)."""
    row = _session_row(report, "session_11")
    streaks = [f for f in row["findings"] if f["kind"] == "STREAK_SKEW"]
    expected = [f for f in _expected_session_row("session_11")["findings"] if f["kind"] == "STREAK_SKEW"]
    assert streaks == expected


def test_pool_mismatch_independent(report: dict[str, Any]) -> None:
    """Unknown item_id phantom must emit POOL_MISMATCH (session_12)."""
    _assert_session_matches(report, "session_12")


def test_duplicate_seq_skips_roll(report: dict[str, Any]) -> None:
    """Repeated roll seq must emit DUPLICATE_SEQ and skip state (session_13)."""
    row = _session_row(report, "session_13")
    dup = next(f for f in row["findings"] if f["kind"] == "DUPLICATE_SEQ")
    expected = next(f for f in _expected_session_row("session_13")["findings"] if f["kind"] == "DUPLICATE_SEQ")
    assert dup == expected


def test_fair_session_clean(report: dict[str, Any]) -> None:
    """Clean five-roll session must be FAIR with zero findings (session_14)."""
    _assert_session_matches(report, "session_14")


def test_pity_forced_does_not_reset(report: dict[str, Any]) -> None:
    """Pity-forced epics must not reset pity counter (session_16)."""
    _assert_session_matches(report, "session_16")


def test_variance_spike_eighth_roll_window(report: dict[str, Any]) -> None:
    """Variance spike after eight logged values in window (session_18)."""
    row = _session_row(report, "session_18")
    spike = next(f for f in row["findings"] if f["kind"] == "VARIANCE_SPIKE")
    expected = next(f for f in _expected_session_row("session_18")["findings"] if f["kind"] == "VARIANCE_SPIKE")
    assert spike == expected


def test_natural_gini_excludes_pity_forced(report: dict[str, Any]) -> None:
    """Pity-forced epics excluded from gini but counted in epic_drops (session_20)."""
    _assert_session_matches(report, "session_20")


def test_session_13_finding_completeness(report: dict[str, Any]) -> None:
    """Duplicate-seq session must match reference findings and stats (session_13)."""
    _assert_session_matches(report, "session_13")


def test_session_04_finding_completeness(report: dict[str, Any]) -> None:
    """Mixed RNG and pity session must match reference (session_04)."""
    _assert_session_matches(report, "session_04")


def test_session_15_finding_completeness(report: dict[str, Any]) -> None:
    """Pity and streak edge session must match reference (session_15)."""
    _assert_session_matches(report, "session_15")


def test_session_19_finding_completeness(report: dict[str, Any]) -> None:
    """Cooldown and pool edge session must match reference (session_19)."""
    _assert_session_matches(report, "session_19")


def test_session_20_finding_completeness(report: dict[str, Any]) -> None:
    """Pity-forced epic gini edge session must match reference (session_20)."""
    _assert_session_matches(report, "session_20")


def test_session_06_finding_completeness(report: dict[str, Any]) -> None:
    """Chi-square tier stats session must match reference (session_06)."""
    _assert_session_matches(report, "session_06")


def test_session_11_finding_completeness(report: dict[str, Any]) -> None:
    """Streak skew session must match reference (session_11)."""
    _assert_session_matches(report, "session_11")


def test_session_17_finding_completeness(report: dict[str, Any]) -> None:
    """Encounter-order vs sorted-seq anchor session must match reference (session_17)."""
    _assert_session_matches(report, "session_17")


def test_session_03_finding_completeness(report: dict[str, Any]) -> None:
    """Inclusive pity threshold session must match reference (session_03)."""
    _assert_session_matches(report, "session_03")


def test_session_08_finding_completeness(report: dict[str, Any]) -> None:
    """RNG and selection edge session must match reference (session_08)."""
    _assert_session_matches(report, "session_08")


def test_session_09_finding_completeness(report: dict[str, Any]) -> None:
    """Tier weight edge session must match reference (session_09)."""
    _assert_session_matches(report, "session_09")


def test_session_10_finding_completeness(report: dict[str, Any]) -> None:
    """Mixed gate session must match reference (session_10)."""
    _assert_session_matches(report, "session_10")


def test_session_12_finding_completeness(report: dict[str, Any]) -> None:
    """Pool mismatch session must match reference (session_12)."""
    _assert_session_matches(report, "session_12")


def test_session_16_finding_completeness(report: dict[str, Any]) -> None:
    """Pity forced counter session must match reference (session_16)."""
    _assert_session_matches(report, "session_16")


def test_session_18_finding_completeness(report: dict[str, Any]) -> None:
    """Variance spike session must match reference (session_18)."""
    _assert_session_matches(report, "session_18")


def test_catalog_all_twenty_sessions_match_reference(report: dict[str, Any]) -> None:
    """Every catalog session row must byte-match the independent reference engine."""
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    assert len(catalog["sessions"]) == SESSION_COUNT
    for session_id in catalog["sessions"]:
        _assert_session_matches(report, session_id)


def test_roll_replay_requires_seq_sort(report: dict[str, Any]) -> None:
    """Reversed JSON roll array order must not change replay output (session_02)."""
    path = VAULT_DIR / "session_02.json"
    clean = VERIFIER_DIR / "session_02_roll_order_clean.json"
    if not clean.is_file():
        shutil.copy(path, clean)
    baseline_row = _normalize_session_row(_session_row(report, "session_02"))

    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["rolls"] = list(reversed(obj["rolls"]))
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    try:
        assert _run_make("run", "perturb_roll_order.log", fail_hard=True)
        perturbed_report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        perturbed_row = _normalize_session_row(_session_row(perturbed_report, "session_02"))
        assert perturbed_row == baseline_row
    finally:
        shutil.copy(clean, path)

    assert _run_make("run", "perturb_roll_order_restore.log", fail_hard=True)
    restored_report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    restored_row = _normalize_session_row(_session_row(restored_report, "session_02"))
    assert restored_row == baseline_row


def test_perturbed_session_changes_report_then_restores(report: dict[str, Any]) -> None:
    """Anti-cheat: perturbing session_14 must change replay output; restore yields baseline."""
    path = VAULT_DIR / "session_14.json"
    clean = VERIFIER_DIR / "session_14_clean.json"
    if not clean.is_file():
        shutil.copy(path, clean)
    baseline_row = _normalize_session_row(_session_row(report, "session_14"))

    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["rolls"][0]["roll_value"] = float(obj["rolls"][0]["roll_value"]) + 0.001
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    try:
        assert _run_make("run", "perturb_run.log", fail_hard=True)
        perturbed_report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        perturbed_row = _normalize_session_row(_session_row(perturbed_report, "session_14"))
        assert perturbed_row != baseline_row
    finally:
        shutil.copy(clean, path)

    assert _run_make("run", "perturb_restore.log", fail_hard=True)
    restored_report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    restored_row = _normalize_session_row(_session_row(restored_report, "session_14"))
    assert restored_row == baseline_row


def test_report_contract_and_determinism(report: dict[str, Any]) -> None:
    """Compact JSON bytes, immutability guards, and consecutive make run determinism."""
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    assert [r["session_id"] for r in report["sessions"]] == catalog["sessions"]
    assert len(report["sessions"]) == SESSION_COUNT

    for path in APP_DIR.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(APP_DIR).as_posix()
        if rel.startswith(("rollbench/", "faircore/", "out/")):
            continue
        assert rel in IMMUTABLE_SHA256, f"untracked path {rel}"
        assert _sha256_file(path) == IMMUTABLE_SHA256[rel], f"modified {rel}"

    for row in report["sessions"]:
        assert "gini_coefficient" in row
        assert "gini" not in row
        if row["gini_coefficient"] == 0:
            assert isinstance(row["gini_coefficient"], int)
        for finding in row["findings"]:
            assert FINDING_ID_RE.match(finding["finding_id"])
            assert finding["kind"] in FINDING_KINDS
            assert finding["player_id"]
        assert row["status"] in ("FAIR", "BIASED")

    raw = REPORT_PATH.read_bytes()
    assert raw.endswith(b"\n") and b": " not in raw and b", " not in raw
    canonical = json.dumps(report, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
    assert raw == canonical
    assert REPORT_FIRST.is_file() and raw == REPORT_FIRST.read_bytes()

    allowed = {"rollbench", "faircore", "out", "dropvault", "go.mod", "Makefile"}
    for entry in APP_DIR.iterdir():
        assert entry.name in allowed, f"unexpected /app/{entry.name}"
    assert (APP_DIR / "out" / "lootfair").is_file()

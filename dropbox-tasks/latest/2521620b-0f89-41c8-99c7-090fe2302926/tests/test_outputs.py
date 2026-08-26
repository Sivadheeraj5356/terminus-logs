"""Verifier for chronctl timeline_report.json — pack revision 2026-06-audit-chain-v4."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NamedTuple

import pytest

APP = Path("/app")
_TESTS_DIR = Path(__file__).resolve().parent
REPORT = Path("/app/output/timeline_report.json")
PACK = Path("/app/data/scenarios.json")
CONFIG = Path("/app/config/defaults.yaml")
GRADING_CONTRACT = Path("/app/config/grading_contract.yaml")
ROTATE_SCHEDULE = Path("/app/config/rotate_schedule.json")
# Agent-controlled binary runs as this UID under a /tests-hidden view.
_AGENT_RUN_USER = "chronrun"
_ISOLATION_ROOT = Path("/var/lib/verifier-isolation")
_MOUNT_NS_OK: bool | None = None

_CHAIN_LINE = "chain_required: true"
HEX64 = re.compile(r"^[0-9a-f]{64}$")

_CLOCK_ROW = "negative_offset_window"
_LEDGER_ROW = "triple_compact_stack"
_TIE_ROW = "interleaved_tie_quad"
_DIGEST_ROW = "mega_dense_lane"
_ZEDPAIR_ROW = "cascade_tie_storm"
_TRIPLE_OVERLAP_ROW = "offset_compact_tie"
_HARD_CROSS_ROWS = [
    "offset_lane_cross",
    "compact_pair_merge",
    "interleaved_tie_quad",
    _DIGEST_ROW,
    _TRIPLE_OVERLAP_ROW,
    _ZEDPAIR_ROW,
    "skew_nsec_compact",
    "polar_triple_cross",
]
_KEY_BUNDLE_NAMES = {
    "mega_dense_lane",
    "triple_compact_stack",
    "cascade_tie_storm",
    "offset_compact_tie",
    "polar_triple_cross",
}
_KEY_COMPARATIVE_LEFT = {
    "mega_dense_lane",
    "triple_compact_stack",
    "cascade_tie_storm",
    "polar_triple_cross",
    "skew_nsec_compact",
}


def _contract_scalar(key: str) -> str:
    for line in GRADING_CONTRACT.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip('"')
    raise AssertionError(f"{key} missing from grading_contract.yaml")


def _load_grading() -> dict:
    for candidate in _TESTS_DIR.iterdir():
        if candidate.suffix != ".json":
            continue
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        if isinstance(payload.get("scenarios"), dict):
            return payload
    raise AssertionError("missing embedded grading table")


def _load_invariants() -> SimpleNamespace:
    for candidate in _TESTS_DIR.iterdir():
        if candidate.suffix != ".json":
            continue
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        # Distinguishes from pack_grading_table.json (which has a scenarios dict).
        if isinstance(payload.get("compact_rows"), list):
            return SimpleNamespace(**payload)
    raise AssertionError("pack invariants missing from /tests")


_PACK_DATA = json.loads(PACK.read_text(encoding="utf-8"))
_ROTATE = json.loads(ROTATE_SCHEDULE.read_text(encoding="utf-8"))
_GRADING = _load_grading()
PACK_ORDER = [sc["name"] for sc in _PACK_DATA["scenarios"]]
PACK_INTEGRITY_SHA256 = _contract_scalar("pack_integrity_sha256")
_INV = _load_invariants()
_FINISH_STATE = _contract_scalar("finish_state")
NORM_LANE_ROWS = _INV.norm_lane_rows
ANCHOR_LANE_ROWS = _INV.anchor_lane_rows
TIE_LANE_ROWS = _INV.tie_lane_rows
HEAD_HEX_DIFF_PAIRS = _INV.head_hex_must_differ_pairs
SECTOR_ROWS = _INV.sector_rows
SECTOR_EXACT_TOTALS = _INV.sector_exact_totals
REPORT_TOP_KEYS = _INV.report_top_keys
COMPARATIVE_CHECKS = _INV.comparative_checks
CROSS_FIELD_CHECKS = _INV.cross_field_checks
REPORT_ROW_KEYS = _INV.report_row_keys
_EXACT_TOTAL_EVENTS = int(_contract_scalar("exact_total_events"))
_MIN_SCENARIOS = int(_contract_scalar("min_scenario_count"))
_MIN_TOTAL_EVENTS = int(_contract_scalar("min_total_events"))
HARD_EDGE_ROWS = _INV.hard_edge_rows
HARD_EDGE_SECTOR = _INV.hard_edge_sector
TRIPLE_LANE_OVERLAP_ROWS = _INV.triple_lane_overlap_rows
_RECOMPUTE_FIELDS = (
    "active_session_epoch",
    "events_replayed",
    "chain_intact",
    "order_drift_count",
    "contradiction_count",
    "witness_ok_count",
    "timeline_head_hex",
)
_KEY_BUNDLES = [b for b in CROSS_FIELD_CHECKS if b["name"] in _KEY_BUNDLE_NAMES]
_KEY_COMPARATIVES = [c for c in COMPARATIVE_CHECKS if c["left"] in _KEY_COMPARATIVE_LEFT]
_KEY_HEAD_HEX_PAIRS = HEAD_HEX_DIFF_PAIRS[:5]


def _yaml_scalar(key: str) -> str:
    for line in CONFIG.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip('"')
    raise AssertionError(f"{key} missing from defaults.yaml")


_INTACT_OK = int(_yaml_scalar("intact_ok_value"))


def _expected(name: str) -> dict:
    return _GRADING["scenarios"][name]


def _sha256_file(path: Path) -> str:
    target = str(path)
    if path == PACK:
        target = "/app/data/scenarios.json"
    out = subprocess.run(
        ["sha256sum", target],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout.split()[0]


def _norm_instant(sec: int, nsec: int, offset_min: int) -> int:
    return sec * 1_000_000_000 + nsec - offset_min * 60 * 1_000_000_000


def _base_pick(left: int, right: int) -> int:
    return left if left <= right else right


def _prefer_left(left_base: int, right_base: int) -> bool:
    return left_base <= right_base


def _span_take(left_count: int, right_count: int) -> int:
    _ = right_count
    return left_count


def _tie_rank(wall: int, anchor: int, seg_id: int, seq: int) -> str:
    return f"{wall:020d}-{anchor:06d}-{seg_id:06d}-{seq:08d}"


def _mix_hex(actions: list[str]) -> str:
    payload = b""
    if actions:
        payload = "|".join(actions).encode()
    out = subprocess.run(
        ["sha256sum"],
        input=payload,
        check=True,
        capture_output=True,
    )
    return out.stdout.decode().split()[0]


def _bind_head(epoch: int, actions: list[str]) -> str:
    material = f"{epoch}:{_mix_hex(actions)}".encode()
    out = subprocess.run(
        ["sha256sum"],
        input=material,
        check=True,
        capture_output=True,
    )
    return out.stdout.decode().split()[0]


def _bind_prior(prior_hex: str, local_seal: str) -> str:
    material = f"{prior_hex}:{local_seal}".encode()
    out = subprocess.run(
        ["sha256sum"],
        input=material,
        check=True,
        capture_output=True,
    )
    return out.stdout.decode().split()[0]


def _epoch_bump(pack_events_before: int) -> int:
    total = 0
    for th in _ROTATE.get("thresholds", []):
        if pack_events_before >= int(th["after_events"]):
            total += int(th["epoch_bump"])
    return total


def _genesis_prior() -> str:
    return str(_ROTATE.get("genesis_prior") or "genesis")


class _Ev(NamedTuple):
    sid: int
    oseq: int
    eff: int
    wall: int
    action: str
    anchor: int


def _event_key(ev: _Ev) -> str:
    return f"{ev.sid * 1_000_000 + ev.oseq:04d}:{ev.action}"


def _recompute_scenario(
    sc: dict, prior_hex: str, pack_events_before: int
) -> dict[str, Any]:
    seg_by_id = {s["id"]: s for s in sc["segments"]}
    bases = {s["id"]: s["base_seq"] for s in sc["segments"]}
    anchors = {s["id"]: s["id"] for s in sc["segments"]}

    for step in sc.get("compact", []):
        left_base = bases[step["left"]]
        right_base = bases[step["right"]]
        merged = _base_pick(left_base, right_base)
        left_count = len(seg_by_id[step["left"]]["events"])
        right_count = len(seg_by_id[step["right"]]["events"])
        bases[step["right"]] = merged + _span_take(left_count, right_count)
        if _prefer_left(left_base, right_base):
            anchors[step["right"]] = anchors[step["left"]]

    events: list[_Ev] = []
    for seg in sc["segments"]:
        base = bases[seg["id"]]
        anchor = anchors[seg["id"]]
        for row in seg["events"]:
            wall = _norm_instant(row["sec"], row["nsec"], seg["offset_min"])
            effective = base + (row["seq"] - 1)
            events.append(
                _Ev(
                    sid=seg["id"],
                    oseq=row["seq"],
                    eff=effective,
                    wall=wall,
                    action=row["action"],
                    anchor=anchor,
                )
            )

    active_epoch = int(sc["session_epoch"]) + _epoch_bump(pack_events_before)
    if not events:
        local = _bind_head(active_epoch, [])
        return {
            "active_session_epoch": active_epoch,
            "events_replayed": 0,
            "chain_intact": _INTACT_OK,
            "order_drift_count": 0,
            "contradiction_count": 0,
            "witness_ok_count": 0,
            "timeline_head_hex": _bind_prior(prior_hex, local),
        }

    canonical = sorted(events, key=lambda e: (e.eff, e.sid, e.oseq))
    replay = sorted(
        events, key=lambda e: _tie_rank(e.wall, e.anchor, e.sid, e.eff)
    )

    def inversion_count(can: list[_Ev], rep: list[_Ev]) -> int:
        pos = {_event_key(e): i for i, e in enumerate(can)}
        inv = 0
        for i in range(len(rep)):
            for j in range(i + 1, len(rep)):
                if pos[_event_key(rep[i])] > pos[_event_key(rep[j])]:
                    inv += 1
        return inv

    def tie_contradictions(rep: list[_Ev]) -> int:
        count = 0
        for i in range(len(rep)):
            for j in range(i + 1, len(rep)):
                if rep[i].wall != rep[j].wall:
                    continue
                if rep[i].eff > rep[j].eff:
                    count += 1
        return count

    def witness_matches(can: list[_Ev], rep: list[_Ev]) -> int:
        can_keys = [_event_key(e) for e in can]
        rep_keys = [_event_key(e) for e in rep]
        ok = 0
        for i in range(len(can)):
            if i < len(rep_keys) and rep_keys[i] == can_keys[i]:
                ok += 1
        return ok

    order_drift = inversion_count(canonical, replay)
    contradiction = tie_contradictions(replay)
    replay_actions = [e.action for e in replay]
    local = _bind_head(active_epoch, replay_actions)

    return {
        "active_session_epoch": active_epoch,
        "events_replayed": len(events),
        "chain_intact": _INTACT_OK if order_drift == 0 and contradiction == 0 else 0,
        "order_drift_count": order_drift,
        "contradiction_count": contradiction,
        "witness_ok_count": witness_matches(canonical, replay),
        "timeline_head_hex": _bind_prior(prior_hex, local),
    }


def _recompute_pack(pack_data: dict) -> dict[str, dict[str, Any]]:
    prior = _genesis_prior()
    cum = 0
    out: dict[str, dict[str, Any]] = {}
    for sc in pack_data["scenarios"]:
        row = _recompute_scenario(sc, prior, cum)
        out[sc["name"]] = row
        prior = row["timeline_head_hex"]
        cum += int(row["events_replayed"])
    return out


def _want_row(name: str) -> dict[str, Any]:
    return _recompute_pack(_PACK_DATA)[name]


def _setpriv_agent_cmd(argv: list[str]) -> list[str]:
    """Drop to chronrun with no-new-privs so setuid wrappers cannot re-escalate."""
    return [
        "setpriv",
        f"--reuid={_AGENT_RUN_USER}",
        f"--regid={_AGENT_RUN_USER}",
        "--clear-groups",
        "--no-new-privs",
        "--",
        *argv,
    ]


def _mount_ns_available() -> bool:
    """True when a private user+mount namespace can hide /tests via tmpfs."""
    global _MOUNT_NS_OK
    if _MOUNT_NS_OK is None:
        proc = subprocess.run(
            [
                "unshare",
                "--user",
                "--map-root-user",
                "--mount",
                "true",
            ],
            check=False,
            capture_output=True,
        )
        _MOUNT_NS_OK = proc.returncode == 0
    return _MOUNT_NS_OK


def _assert_grading_markers_absent() -> None:
    """Fail closed if the agent UID can still see /tests grading artifacts."""
    probe = subprocess.run(
        _setpriv_agent_cmd(
            [
                "bash",
                "-c",
                "for f in /tests/pack_grading_table.json "
                "/tests/pack_invariants.json /tests/test_outputs.py; do "
                '  test -e "$f" && exit 7; '
                "done; exit 0",
            ]
        ),
        check=False,
        capture_output=True,
    )
    if probe.returncode != 0:
        raise AssertionError(
            "verifier isolation broken: /tests grading artifacts still visible"
        )


def _run_via_mount_namespace(
    argv: list[str], **kwargs: Any
) -> subprocess.CompletedProcess:
    """Hide /tests with a tmpfs in a private mount namespace, then run chronctl.

    Inside ``--map-root-user`` only uid 0 is mapped, so we cannot drop to
    chronrun there; the tmpfs hide alone keeps grading files unreachable.
    """
    hide_and_exec = (
        "mount -t tmpfs -o size=1M,mode=000,nosuid,nodev,noexec tmpfs /tests && "
        "for f in /tests/pack_grading_table.json /tests/pack_invariants.json "
        "/tests/test_outputs.py; do "
        '  if [ -e "$f" ]; then echo "isolation broken: $f" >&2; exit 99; fi; '
        "done && "
        'exec "$@"'
    )
    cmd = [
        "unshare",
        "--user",
        "--map-root-user",
        "--mount",
        "bash",
        "-c",
        hide_and_exec,
        "chron-isolate",
        *argv,
    ]
    return subprocess.run(cmd, **kwargs)


def _run_via_tests_stash(
    argv: list[str], **kwargs: Any
) -> subprocess.CompletedProcess:
    """Move /tests out of the tree for the chronctl process lifetime.

    Used when mount namespaces are blocked (common default Docker seccomp).
    Harbor uploads /tests as a normal directory, so rename works.
    """
    tests = Path("/tests")
    _ISOLATION_ROOT.mkdir(parents=True, exist_ok=True)
    os.chmod(_ISOLATION_ROOT, 0o700)
    stash = _ISOLATION_ROOT / f"tests-{os.urandom(16).hex()}"
    if stash.exists():
        shutil.rmtree(stash)
    moved = False
    if tests.is_dir():
        tests.rename(stash)
        moved = True
        try:
            os.chmod(stash, 0o700)
        except OSError:
            pass
        tests.mkdir(mode=0o000)
        try:
            os.chmod(tests, 0o000)
        except OSError:
            pass
    try:
        _assert_grading_markers_absent()
        return subprocess.run(_setpriv_agent_cmd(argv), **kwargs)
    finally:
        if moved:
            if tests.exists():
                if tests.is_dir():
                    try:
                        tests.rmdir()
                    except OSError:
                        shutil.rmtree(tests)
                else:
                    tests.unlink()
            stash.rename(tests)


def _prepare_agent_write_path(path: Path) -> None:
    """Make out_path reachable/writable for the unprivileged chronctl UID.

    Always end with mode 0777 on the parent. Under ``unshare --map-root-user``
    only the caller's host uid is mapped, so a chronrun-owned 0755 directory
    is not writable on hosts where the verifier is not real root (e.g. Daytona).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    # Walk parents up to /tmp or /app so chronrun can traverse pytest tmp dirs.
    cur = path.parent
    for _ in range(8):
        try:
            st = cur.stat()
            os.chmod(cur, st.st_mode | 0o755)
        except OSError:
            break
        if cur in (Path("/"), Path("/tmp"), Path("/app")):
            break
        cur = cur.parent
    # Mount-namespace isolation runs chronctl as the caller uid (map-root-user),
    # not chronrun; chowning here breaks writes on non-root hosts (Daytona).
    if not _mount_ns_available():
        try:
            shutil.chown(path.parent, user=_AGENT_RUN_USER, group=_AGENT_RUN_USER)
        except OSError:
            pass
    try:
        os.chmod(path.parent, 0o777)
    except OSError:
        pass


def _run_agent_chronctl(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    """Run agent-controlled chronctl with /tests not accessible in its view."""
    if _mount_ns_available():
        return _run_via_mount_namespace(argv, **kwargs)
    return _run_via_tests_stash(argv, **kwargs)


def rebuild_chronctl() -> None:
    go_bin = Path("/usr/local/go/bin/go")
    if not go_bin.is_file():
        pytest.skip("go toolchain not available")
    subprocess.run(
        [
            "/usr/local/go/bin/go",
            "build",
            "-buildvcs=false",
            "-o",
            "/app/chronctl",
            "./cmd/chronctl",
        ],
        cwd="/app",
        check=True,
    )
    # World-executable; runtime invocations use a /tests-hidden agent view.
    os.chmod("/app/chronctl", 0o755)


def run_chronctl() -> None:
    _prepare_agent_write_path(REPORT)
    _run_agent_chronctl(
        [
            "/app/chronctl",
            "-pack",
            "/app/data/scenarios.json",
            "-out",
            "/app/output/timeline_report.json",
        ],
        cwd="/app",
        check=True,
    )


def run_chronctl_env(extra: dict[str, str]) -> None:
    env = os.environ.copy()
    env.update(extra)
    _prepare_agent_write_path(REPORT)
    _run_agent_chronctl(
        [
            "/app/chronctl",
            "-pack",
            "/app/data/scenarios.json",
            "-out",
            "/app/output/timeline_report.json",
        ],
        cwd="/app",
        check=True,
        env=env,
    )


def run_chronctl_pack(pack_path: Path, out_path: Path) -> None:
    _prepare_agent_write_path(out_path)
    os.chmod(pack_path, 0o644)
    os.chmod(pack_path.parent, 0o755)
    _run_agent_chronctl(
        [
            "/app/chronctl",
            "-pack",
            str(pack_path),
            "-out",
            str(out_path),
        ],
        cwd="/app",
        check=True,
    )


def run_chronctl_probe(scenario: str) -> dict:
    out = _run_agent_chronctl(
        [
            "/app/chronctl",
            "-pack",
            "/app/data/scenarios.json",
            "-probe",
            scenario,
        ],
        cwd="/app",
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(out.stdout)


@pytest.fixture(scope="module", autouse=True)
def _build_and_run() -> None:
    rebuild_chronctl()
    run_chronctl()


def _load_report() -> dict:
    assert REPORT.is_file(), "timeline_report.json missing"
    return json.loads(REPORT.read_text(encoding="utf-8"))


def _row_by_name(report: dict, name: str) -> dict:
    for row in report["scenarios"]:
        if row["name"] == name:
            return row
    raise AssertionError(f"scenario row missing: {name}")


def _scenario_by_name(name: str) -> dict:
    for sc in _PACK_DATA["scenarios"]:
        if sc["name"] == name:
            return sc
    raise AssertionError(f"pack scenario missing: {name}")


def _rows_by_name(report: dict) -> dict[str, dict]:
    return {row["name"]: row for row in report["scenarios"]}


def _comparative_holds(left: dict, right: dict, field: str, op: str) -> bool:
    lv = left[field]
    rv = right[field]
    if op == "gt":
        return lv > rv
    if op == "lt":
        return lv < rv
    if op == "eq":
        return lv == rv
    raise AssertionError(f"unsupported comparative op: {op}")


def _assert_full_row(row: dict, name: str) -> None:
    exp = _expected(name)
    for key in REPORT_ROW_KEYS:
        assert row[key] == exp[key], f"{name}.{key}"


def _assert_recompute_parity(name: str, row: dict) -> None:
    want = _want_row(name)
    for field in _RECOMPUTE_FIELDS:
        assert row[field] == want[field], f"{name}.{field}"


class TestReportEnvelope:
    def test_report_exists(self) -> None:
        """Report file is written under /app/output."""
        assert REPORT.is_file()

    def test_schema_version(self) -> None:
        """Top-level schema_version matches the grading contract."""
        report = _load_report()
        assert report["schema_version"] == int(_contract_scalar("schema_version"))

    def test_scenario_count_and_order(self) -> None:
        """Scenario rows match pack size and declaration order."""
        report = _load_report()
        names = [row["name"] for row in report["scenarios"]]
        assert len(names) == len(PACK_ORDER)
        assert len(names) >= _MIN_SCENARIOS
        assert names == PACK_ORDER

    def test_pack_integrity(self) -> None:
        """Bundled scenarios.json matches pinned integrity digest."""
        assert _sha256_file(PACK) == PACK_INTEGRITY_SHA256

    def test_config_chain_required(self) -> None:
        """defaults.yaml keeps chain_required enabled."""
        assert _CHAIN_LINE in CONFIG.read_text(encoding="utf-8")


class TestPackCorrectness:
    def test_all_scenarios_match_grading_table(self) -> None:
        """Every scenario row matches embedded grading expectations."""
        report = _load_report()
        for name in PACK_ORDER:
            _assert_full_row(_row_by_name(report, name), name)

    def test_all_scenarios_match_independent_recompute(self) -> None:
        """Independent Python replay agrees with driver output for the full pack."""
        report = _load_report()
        for name in PACK_ORDER:
            _assert_recompute_parity(name, _row_by_name(report, name))


class TestRepresentativeScenarios:
    def test_negative_offset_window_clean(self) -> None:
        """Negative-offset window row clears drift after UTC normalization repair."""
        row = _row_by_name(_load_report(), _CLOCK_ROW)
        assert row["order_drift_count"] == 0
        assert row["chain_intact"] == _INTACT_OK
        _assert_recompute_parity(_CLOCK_ROW, row)

    def test_triple_compact_stack_witnessed(self) -> None:
        """Triple-compact row witnesses every replayed event after merge rebasing."""
        row = _row_by_name(_load_report(), _LEDGER_ROW)
        assert row["witness_ok_count"] == row["events_replayed"] == 5
        assert row["chain_intact"] == _INTACT_OK
        _assert_recompute_parity(_LEDGER_ROW, row)

    def test_interleaved_tie_no_contradiction(self) -> None:
        """Interleaved tie row keeps contradiction at zero with exact head digest."""
        row = _row_by_name(_load_report(), _TIE_ROW)
        assert row["contradiction_count"] == 0
        assert row["order_drift_count"] == 0
        assert row["timeline_head_hex"] == _expected(_TIE_ROW)["timeline_head_hex"]

    def test_mega_dense_head_hex_exact(self) -> None:
        """Pack density leader matches graded replay-order head digest."""
        row = _row_by_name(_load_report(), _DIGEST_ROW)
        assert row["events_replayed"] == 8
        assert row["timeline_head_hex"] == _expected(_DIGEST_ROW)["timeline_head_hex"]
        _assert_recompute_parity(_DIGEST_ROW, row)

    def test_cascade_tie_storm_counters(self) -> None:
        """Cascade tie storm replays six events with zero contradiction drift."""
        row = _row_by_name(_load_report(), _ZEDPAIR_ROW)
        assert row["events_replayed"] == 6
        assert row["contradiction_count"] == 0
        assert row["witness_ok_count"] == 6
        _assert_recompute_parity(_ZEDPAIR_ROW, row)

    def test_offset_compact_tie_full_row(self) -> None:
        """Cross-module overlap row matches full grading after all repairs."""
        assert _TRIPLE_OVERLAP_ROW in TRIPLE_LANE_OVERLAP_ROWS
        row = _row_by_name(_load_report(), _TRIPLE_OVERLAP_ROW)
        assert row["witness_ok_count"] == row["events_replayed"]
        assert row["order_drift_count"] == 0
        assert row["contradiction_count"] == 0
        _assert_full_row(row, _TRIPLE_OVERLAP_ROW)


class TestCrossScenarioRows:
    @pytest.mark.parametrize("name", _HARD_CROSS_ROWS)
    def test_cross_row_matches_grading(self, name: str) -> None:
        """High-interaction scenarios match full grading rows."""
        _assert_full_row(_row_by_name(_load_report(), name), name)

    @pytest.mark.parametrize("name", HARD_EDGE_ROWS)
    def test_sector_tail_recompute_parity(self, name: str) -> None:
        """Pack tail sector rows agree with independent reference recompute."""
        _assert_recompute_parity(name, _row_by_name(_load_report(), name))


class TestPackInvariants:
    def test_global_chain_and_drift_clean(self) -> None:
        """Full pack reports intact chains with zero drift after repair."""
        report = _load_report()
        for row in report["scenarios"]:
            assert row["chain_intact"] == _INTACT_OK
            assert row["order_drift_count"] == 0
            assert row["contradiction_count"] == 0
            assert row["witness_ok_count"] == row["events_replayed"]

    def test_exact_total_events_replayed(self) -> None:
        """Summed events_replayed matches the pinned exact_total_events budget."""
        report = _load_report()
        total = sum(row["events_replayed"] for row in report["scenarios"])
        assert total == _EXACT_TOTAL_EVENTS
        assert total >= _MIN_TOTAL_EVENTS

    def test_all_head_hex_values_unique(self) -> None:
        """No two scenarios share the same timeline head digest."""
        report = _load_report()
        heads = [row["timeline_head_hex"] for row in report["scenarios"]]
        assert len(heads) == len(set(heads))
        for head in heads:
            assert HEX64.match(head)

    @pytest.mark.parametrize("pair", _KEY_HEAD_HEX_PAIRS)
    def test_head_hex_pairwise_unique(self, pair: list[str]) -> None:
        """Distinct scenario pairs produce distinct timeline head digests."""
        report = _load_report()
        left = _row_by_name(report, pair[0])["timeline_head_hex"]
        right = _row_by_name(report, pair[1])["timeline_head_hex"]
        assert left != right

    @pytest.mark.parametrize("bundle", _KEY_BUNDLES)
    def test_cross_field_bundle(self, bundle: dict) -> None:
        """High-signal scenarios satisfy multi-field counter bundles."""
        row = _row_by_name(_load_report(), bundle["name"])
        for key, value in bundle.items():
            if key == "name":
                continue
            assert row[key] == value

    @pytest.mark.parametrize("check", _KEY_COMPARATIVES)
    def test_comparative_ordering(self, check: dict) -> None:
        """Declared scenario pairs satisfy pack comparative relations."""
        report = _load_report()
        by_name = _rows_by_name(report)
        left = by_name[check["left"]]
        right = by_name[check["right"]]
        assert _comparative_holds(left, right, check["field"], check["op"])

    @pytest.mark.parametrize("sector,exact", list(zip(SECTOR_ROWS, SECTOR_EXACT_TOTALS)))
    def test_sector_exact_event_total(self, sector: list[str], exact: int) -> None:
        """Each sector replays exactly its pinned combined event budget."""
        report = _load_report()
        total = sum(_row_by_name(report, name)["events_replayed"] for name in sector)
        assert total == exact

    def test_hard_edge_sector_exact_events(self) -> None:
        """Hard-edge sector replays exactly seventeen combined events."""
        report = _load_report()
        total = sum(_row_by_name(report, name)["events_replayed"] for name in HARD_EDGE_SECTOR)
        assert total == 17


class TestDeterminism:
    def test_repeat_run_byte_identical(self) -> None:
        """Back-to-back runs emit identical report bytes."""
        first = REPORT.read_bytes()
        run_chronctl()
        second = REPORT.read_bytes()
        assert first == second

    def test_fast_skip_env_ignored(self) -> None:
        """CHRONCTL_FAST_SKIP must not change report output."""
        baseline = _load_report()
        run_chronctl_env({"CHRONCTL_FAST_SKIP": "1"})
        after = _load_report()
        assert baseline == after

    def test_rebuild_then_run_matches_grading(self) -> None:
        """Fresh compile still produces the embedded grading table."""
        rebuild_chronctl()
        run_chronctl()
        report = _load_report()
        for name in PACK_ORDER:
            _assert_full_row(_row_by_name(report, name), name)


class TestProbeInterface:
    @pytest.mark.parametrize(
        "name",
        ["quiet_baseline", "mega_dense_lane", "polar_triple_cross"],
    )
    def test_probe_row_matches_report(self, name: str) -> None:
        """Probe mode emits the same counter row as the full report for a scenario."""
        report_row = _row_by_name(_load_report(), name)
        probe_row = run_chronctl_probe(name)
        for key in REPORT_ROW_KEYS:
            assert probe_row[key] == report_row[key]

    def test_probe_unknown_scenario_exits_nonzero(self) -> None:
        """Probe rejects names that are not present in the pack."""
        proc = _run_agent_chronctl(
            ["/app/chronctl", "-pack", "/app/data/scenarios.json", "-probe", "not_in_pack"],
            cwd="/app",
            capture_output=True,
            text=True,
        )
        assert proc.returncode != 0

    def test_probe_midpack_reflects_rotate_and_prior(self) -> None:
        """Mid-pack probe must carry rotate bump and pack-prefix head binding."""
        name = "mega_dense_lane"
        want = _want_row(name)
        probe_row = run_chronctl_probe(name)
        assert probe_row["active_session_epoch"] == want["active_session_epoch"]
        assert probe_row["timeline_head_hex"] == want["timeline_head_hex"]
        base_epoch = int(_scenario_by_name(name)["session_epoch"])
        assert probe_row["active_session_epoch"] != base_epoch


class TestMutationSensitivity:
    def test_wall_time_mutation_changes_timeline_head(self, tmp_path: Path) -> None:
        """Changing replayed event wall time in a copied pack must change head digest."""
        base_report = _load_report()
        target = "compact_pair_merge"
        before = _row_by_name(base_report, target)["timeline_head_hex"]

        mutated = json.loads(json.dumps(_PACK_DATA))
        for sc in mutated["scenarios"]:
            if sc["name"] == target:
                sc["segments"][0]["events"][1]["sec"] = 1700000305
                break
        mut_pack = tmp_path / "mutated_pack.json"
        mut_pack.write_text(json.dumps(mutated), encoding="utf-8")
        mut_out = tmp_path / "mutated_report.json"
        run_chronctl_pack(mut_pack, mut_out)
        after = _row_by_name(json.loads(mut_out.read_text()), target)["timeline_head_hex"]
        assert after != before

    def test_session_epoch_mutation_changes_timeline_head(self, tmp_path: Path) -> None:
        """Changing session_epoch must change the epoch-bound custody head digest."""
        target = "quiet_baseline"
        before = _row_by_name(_load_report(), target)["timeline_head_hex"]
        mutated = json.loads(json.dumps(_PACK_DATA))
        for sc in mutated["scenarios"]:
            if sc["name"] == target:
                sc["session_epoch"] = int(sc["session_epoch"]) + 17
                break
        mut_pack = tmp_path / "mutated_epoch_pack.json"
        mut_pack.write_text(json.dumps(mutated), encoding="utf-8")
        mut_out = tmp_path / "mutated_epoch_report.json"
        run_chronctl_pack(mut_pack, mut_out)
        after = _row_by_name(json.loads(mut_out.read_text()), target)["timeline_head_hex"]
        assert after != before
        want = _recompute_pack(mutated)[target]
        assert after == want["timeline_head_hex"]

    def test_action_mutation_changes_replay_counters(self, tmp_path: Path) -> None:
        """Mutated replay actions must not leave replay counters identical to baseline."""
        base_row = _row_by_name(_load_report(), "compact_pair_merge")

        mutated = json.loads(json.dumps(_PACK_DATA))
        for sc in mutated["scenarios"]:
            if sc["name"] == "compact_pair_merge":
                sc["segments"][0]["events"][0]["action"] = "gate_open_mut"
                break
        mut_pack = tmp_path / "mutated_pack2.json"
        mut_pack.write_text(json.dumps(mutated), encoding="utf-8")
        mut_out = tmp_path / "mutated_report2.json"
        run_chronctl_pack(mut_pack, mut_out)
        mut_row = _row_by_name(json.loads(mut_out.read_text()), "compact_pair_merge")
        changed = (
            mut_row["order_drift_count"] != base_row["order_drift_count"]
            or mut_row["contradiction_count"] != base_row["contradiction_count"]
            or mut_row["timeline_head_hex"] != base_row["timeline_head_hex"]
            or mut_row["witness_ok_count"] != base_row["witness_ok_count"]
        )
        assert changed

    def test_early_action_mutation_shifts_later_pack_heads(self, tmp_path: Path) -> None:
        """Changing an early scenario action must change a later row's pack-bound head."""
        later = "polar_triple_cross"
        before = _row_by_name(_load_report(), later)["timeline_head_hex"]
        mutated = json.loads(json.dumps(_PACK_DATA))
        for sc in mutated["scenarios"]:
            if sc["name"] == "quiet_baseline":
                sc["segments"][0]["events"][0]["action"] = "quiet_mut_head"
                break
        mut_pack = tmp_path / "mutated_prefix_pack.json"
        mut_pack.write_text(json.dumps(mutated), encoding="utf-8")
        mut_out = tmp_path / "mutated_prefix_report.json"
        run_chronctl_pack(mut_pack, mut_out)
        after = _row_by_name(json.loads(mut_out.read_text()), later)["timeline_head_hex"]
        assert after != before
        want = _recompute_pack(mutated)[later]
        assert after == want["timeline_head_hex"]

    def test_prefix_event_injection_changes_active_epoch(self, tmp_path: Path) -> None:
        """Injecting enough early events to cross a rotate band must change a later epoch."""
        target = "negative_offset_window"
        before = _row_by_name(_load_report(), target)["active_session_epoch"]
        mutated = json.loads(json.dumps(_PACK_DATA))
        for sc in mutated["scenarios"]:
            if sc["name"] == "quiet_baseline":
                base_seq = max(row["seq"] for row in sc["segments"][0]["events"])
                for i in range(1, 21):
                    sc["segments"][0]["events"].append(
                        {
                            "seq": base_seq + i,
                            "sec": 1700000000 + i,
                            "nsec": 0,
                            "action": "quiet_extra_evt",
                        }
                    )
                break
        mut_pack = tmp_path / "mutated_rotate_pack.json"
        mut_pack.write_text(json.dumps(mutated), encoding="utf-8")
        mut_out = tmp_path / "mutated_rotate_report.json"
        run_chronctl_pack(mut_pack, mut_out)
        after_row = _row_by_name(json.loads(mut_out.read_text()), target)
        assert after_row["active_session_epoch"] != before
        want = _recompute_pack(mutated)[target]
        assert after_row["active_session_epoch"] == want["active_session_epoch"]
        assert after_row["timeline_head_hex"] == want["timeline_head_hex"]


class TestRotateAndPackBinding:
    def test_active_epochs_follow_rotate_schedule(self) -> None:
        """Pack-cumulative rotate bumps must appear in active_session_epoch."""
        report = _load_report()
        want = _recompute_pack(_PACK_DATA)
        bumped = 0
        for name in PACK_ORDER:
            row = _row_by_name(report, name)
            assert row["active_session_epoch"] == want[name]["active_session_epoch"]
            if row["active_session_epoch"] != _scenario_by_name(name)["session_epoch"]:
                bumped += 1
        assert bumped >= 5

    def test_pack_heads_form_prior_chain(self) -> None:
        """Each timeline_head_hex must bind the previous row's head (or genesis)."""
        report = _load_report()
        want = _recompute_pack(_PACK_DATA)
        for name in PACK_ORDER:
            row = _row_by_name(report, name)
            assert row["timeline_head_hex"] == want[name]["timeline_head_hex"]
            assert HEX64.match(row["timeline_head_hex"])

    def test_unconditional_intact_rejected_when_drift_present(self) -> None:
        """chain_intact must not stay set when drift or contradiction is nonzero."""
        report = _load_report()
        for row in report["scenarios"]:
            if row["order_drift_count"] > 0 or row["contradiction_count"] > 0:
                assert row["chain_intact"] != _INTACT_OK

    def test_forced_tie_inversion_clears_intact(self, tmp_path: Path) -> None:
        """Equal-wall events with inverted effective/anchor order must clear intact."""
        mutated = json.loads(json.dumps(_PACK_DATA))
        for sc in mutated["scenarios"]:
            if sc["name"] != "quiet_baseline":
                continue
            sc["segments"] = [
                {
                    "id": 1,
                    "base_seq": 200,
                    "offset_min": 0,
                    "events": [
                        {
                            "seq": 1,
                            "sec": 1700000000,
                            "nsec": 0,
                            "action": "hi_eff_low_anchor",
                        }
                    ],
                },
                {
                    "id": 2,
                    "base_seq": 10,
                    "offset_min": 0,
                    "events": [
                        {
                            "seq": 1,
                            "sec": 1700000000,
                            "nsec": 0,
                            "action": "lo_eff_hi_anchor",
                        }
                    ],
                },
            ]
            sc["compact"] = []
            break
        mut_pack = tmp_path / "mutated_neg_intact.json"
        mut_pack.write_text(json.dumps(mutated), encoding="utf-8")
        mut_out = tmp_path / "mutated_neg_intact_report.json"
        run_chronctl_pack(mut_pack, mut_out)
        row = _row_by_name(json.loads(mut_out.read_text()), "quiet_baseline")
        want = _recompute_pack(mutated)["quiet_baseline"]
        assert want["contradiction_count"] > 0
        assert want["chain_intact"] != _INTACT_OK
        assert row["contradiction_count"] == want["contradiction_count"]
        assert row["chain_intact"] == want["chain_intact"]
        assert row["chain_intact"] != _INTACT_OK


class TestIntegrityGuards:
    def test_report_schema_keys(self) -> None:
        """Report exposes only declared top-level keys and row fields."""
        report = _load_report()
        assert sorted(report.keys()) == sorted(REPORT_TOP_KEYS)
        sample = _row_by_name(report, PACK_ORDER[0])
        assert sorted(sample.keys()) == sorted(REPORT_ROW_KEYS)

    def test_chain_intact_zero_requires_drift_signal(self) -> None:
        """Rows with chain_intact unset must show order or contradiction drift."""
        report = _load_report()
        for row in report["scenarios"]:
            if row["chain_intact"] == _INTACT_OK:
                continue
            assert row["order_drift_count"] > 0 or row["contradiction_count"] > 0

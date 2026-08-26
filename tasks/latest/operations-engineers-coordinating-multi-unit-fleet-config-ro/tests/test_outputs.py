"""Fleet rollout planner verifier — system-administration artifact contracts."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_SUPPORT = Path(__file__).resolve().parent / "verifier-support"
if str(_SUPPORT) not in sys.path:
    sys.path.insert(0, str(_SUPPORT))
import digest_math  # noqa: E402

APP = Path("/app")
ODIP_BIN = "/app/bin/odip"
POLICY = APP / "fixtures" / "policies" / "approval_policy.json"
LATTICE_DEFAULT = Path("/app/state/odip/impact_lattice.json")
PLAN_DEFAULT = Path("/app/output/decision_impact_plan.json")
JOURNAL_DEFAULT = Path("/app/state/odip/rollout_journal.jsonl")
SCENARIO_ROOT = APP / "fixtures" / "scenarios"
HOLD_ROOT = Path("/opt/verifier-fixtures/odip-holdout")
HOLD_SEAL_ROOT = Path("/opt/verifier-fixtures/odip-holdout-seal")
HOLD_SLOT_ROOT = Path("/opt/verifier-fixtures/odip-holdout-slot")

FLEET_DOCS = [
    APP / "docs" / "org-decision-planning-workflow.md",
    APP / "docs" / "dependency-closure-contract.md",
    APP / "docs" / "impact-propagation-contract.md",
    APP / "docs" / "approval-gate-contract.md",
    APP / "docs" / "resource-feasibility-contract.md",
    APP / "docs" / "fleet-rollout-ops.md",
    APP / "docs" / "odip-operator-commands.md",
    APP / "docs" / "holdout-probe-fixtures.md",
    APP / "docs" / "rollout-epoch-seal-contract.md",
    APP / "docs" / "booking-window-slot-contract.md",
]


def _scenario(dir_path: Path) -> dict:
    meta = json.loads((dir_path / "meta.json").read_text(encoding="utf-8"))
    decisions = [
        json.loads(line)
        for line in (dir_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {
        "meta": meta,
        "decisions": decisions,
        "units": json.loads((dir_path / "units.json").read_text(encoding="utf-8")),
        "deps": json.loads((dir_path / "dependencies.json").read_text(encoding="utf-8")),
        "resources": json.loads((dir_path / "resources.json").read_text(encoding="utf-8")),
        "topology": json.loads((dir_path / "topology.json").read_text(encoding="utf-8")),
    }


def _fanout(decisions, topo_edges):
    children: dict[str, list[str]] = {}
    for e in topo_edges:
        children.setdefault(e["parent"], []).append(e["child"])
    rows = []
    for d in decisions:
        seen: set[str] = set()
        stack = list(d["direct_units"])
        while stack:
            u = stack.pop()
            if u in seen:
                continue
            seen.add(u)
            stack.extend(c for c in children.get(u, []) if c not in seen)
        units = sorted(seen)
        rows.append(
            {"decision_id": d["id"], "affected_units": units, "impact_score": len(units)}
        )
    rows.sort(key=lambda r: r["decision_id"])
    return rows


def _cycle(ids, edges):
    adj = {i: [] for i in ids}
    for e in edges:
        adj[e["from"]].append(e["to"])
    for k in adj:
        adj[k].sort()
    color = {i: 0 for i in ids}
    parent: dict[str, str] = {}
    found = None

    def dfs(u: str) -> bool:
        nonlocal found
        color[u] = 1
        for v in adj[u]:
            if color[v] == 0:
                parent[v] = u
                if dfs(v):
                    return True
            elif color[v] == 1:
                path = [v]
                cur = u
                while cur != v and cur in parent:
                    path.append(cur)
                    cur = parent[cur]
                path.append(v)
                path = list(reversed(path))
                if len(path) > 1 and path[0] == path[-1]:
                    path = path[:-1]
                if path:
                    mi = min(range(len(path)), key=lambda i: path[i])
                    path = path[mi:] + path[:mi]
                found = path
                return True
        color[u] = 2
        return False

    for i in sorted(ids):
        if color[i] == 0 and dfs(i):
            return True, found or []
    return False, []


def _kahn(ids, edges):
    indeg = {i: 0 for i in ids}
    adj = {i: [] for i in ids}
    for e in edges:
        adj[e["from"]].append(e["to"])
        indeg[e["to"]] += 1
    for k in adj:
        adj[k].sort()
    ready = sorted(i for i in ids if indeg[i] == 0)
    order = []
    while ready:
        u = ready.pop(0)
        order.append(u)
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                ready.append(v)
                ready.sort()
    return order if len(order) == len(ids) else []


def _conflicts(sc, impact_rows):
    out = []
    books = sc["resources"].get("bookings", [])
    for i, a in enumerate(books):
        for b in books[i + 1 :]:
            if a["pool"] != b["pool"] or a["decision_id"] == b["decision_id"]:
                continue
            if a["start"] < b["end"] and b["start"] < a["end"]:
                da, db = sorted([a["decision_id"], b["decision_id"]])
                out.append(
                    {"type": "resource", "pool": a["pool"], "decision_a": da, "decision_b": db}
                )
    affected = {r["decision_id"]: r["affected_units"] for r in impact_rows}
    by_id = {d["id"]: d for d in sc["decisions"]}
    ids = sorted(by_id)
    for i, a in enumerate(ids):
        for b in ids[i + 1 :]:
            da, db = by_id[a], by_id[b]
            if not (da.get("exclusive") and db.get("exclusive")):
                continue
            wa, wb = da["window"], db["window"]
            if not (wa["start"] < wb["end"] and wb["start"] < wa["end"]):
                continue
            for u in sorted(set(affected[a]) & set(affected[b])):
                out.append(
                    {"type": "timeline", "unit": u, "decision_a": a, "decision_b": b}
                )
    out.sort(
        key=lambda c: (
            c["type"],
            c.get("pool") or c.get("unit") or "",
            c["decision_a"],
            c["decision_b"],
        )
    )
    return out


def _regs(sc):
    req = sc["meta"].get("required_clearance") or ""
    out = []
    for d in sorted(sc["decisions"], key=lambda x: x["id"]):
        if d["class"] != "region_expand" or not req:
            continue
        if d.get("clearance") != req:
            out.append(
                {"type": "regulatory", "decision_id": d["id"], "reason": "clearance_missing"}
            )
    return out


def _approvals(order, impact_rows, sc, policy):
    score = {r["decision_id"]: r["impact_score"] for r in impact_rows}
    class_by = {d["id"]: d["class"] for d in sc["decisions"]}
    flags_by = {d["id"]: d.get("flags") or [] for d in sc["decisions"]}
    steps = []
    for did in order:
        roles = list(policy["class_gates"].get(class_by[did], []))
        sc_ = score.get(did, 0)
        for th in policy["score_thresholds"]:
            if sc_ >= th["min_score"]:
                for r in th["extra_roles"]:
                    if r not in roles:
                        roles.append(r)
        flag = policy["conditional"]["exception_flag"]
        extra = policy["conditional"]["extra_role"]
        if flag in flags_by.get(did, []) and extra not in roles:
            roles.append(extra)
        steps.append({"decision_id": did, "roles": roles})
    return steps


def _epoch_seal(lattice_digest: str, epoch: int, scenario_id: str, topo_rev: str) -> str:
    return digest_math.epoch_seal(lattice_digest, epoch, scenario_id, topo_rev)


def _window_digest(decisions: list[dict]) -> str:
    return digest_math.window_digest(decisions)


def _booking_digest(bookings: list[dict]) -> str:
    return digest_math.booking_digest(bookings)


def reference_fleet_rollout(scenario_dir: Path) -> dict:
    sc = _scenario(scenario_dir)
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    ids = sorted(d["id"] for d in sc["decisions"])
    edges = sc["deps"]["edges"]
    cyc, path = _cycle(ids, edges)
    impacts = _fanout(sc["decisions"], sc["topology"]["edges"])
    order = [] if cyc else _kahn(ids, edges)
    conflicts = _conflicts(sc, impacts)
    regs = _regs(sc)
    meta = sc["meta"]
    bookings = sc["resources"].get("bookings", [])
    return {
        "scenario_id": meta["scenario_id"],
        "rollout_epoch": int(meta.get("rollout_epoch") or 0),
        "topology_revision": meta.get("topology_revision") or "",
        "execution_order": order,
        "approval_steps": _approvals(order, impacts, sc, policy),
        "conflicts": conflicts,
        "regulatory_blocks": regs,
        "feasible": (not cyc) and (not conflicts) and (not regs),
        "cycle_detected": cyc,
        "cycle_path": path,
        "impact_rows": impacts,
        "window_digest": _window_digest(sc["decisions"]),
        "booking_digest": _booking_digest(bookings),
    }


def invoke_rollout(scenario: Path, lattice: Path, plan: Path) -> subprocess.CompletedProcess:
    lattice.parent.mkdir(parents=True, exist_ok=True)
    plan.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            ODIP_BIN,
            "run",
            "--scenario",
            str(scenario),
            "--policy",
            str(POLICY),
            "--stage",
            str(lattice),
            "--out",
            str(plan),
        ],
        cwd="/app",
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="module", autouse=True)
def _rebuild_odip():
    subprocess.run(
        ["go", "build", "-o", "/app/bin/odip", "./cmd/odip"],
        cwd="/app",
        check=True,
        env={**os.environ, "CGO_ENABLED": "0"},
    )


@pytest.fixture(autouse=True)
def _clear_rollout_journal():
    if JOURNAL_DEFAULT.exists():
        JOURNAL_DEFAULT.unlink()
    yield


def test_t61f6d8_fleet_docs_cover_rollout_daemon_and_drift_contracts():
    """Verifies fleet rollout, daemon snapshot, and topology drift docs exist under /app/docs."""
    for p in FLEET_DOCS:
        assert p.is_file(), p


def test_t61f6d8_rollout_stage_writes_lattice_at_contract_path():
    """Verifies stage ingest creates lattice at /app/state/odip/impact_lattice.json with odip.lattice.v1."""
    lattice = Path("/app/state/odip/impact_lattice.json")
    if lattice.exists():
        lattice.unlink()
    r = subprocess.run(
        [
            ODIP_BIN,
            "stage",
            "--scenario",
            str(SCENARIO_ROOT / "dept_merge"),
            "--policy",
            str(POLICY),
            "--out",
            str(lattice),
        ],
        cwd="/app",
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    assert lattice.is_file()
    lat = json.loads(lattice.read_text(encoding="utf-8"))
    assert lat["schema_version"] == "odip.lattice.v1"
    assert lat["scenario_id"] == "dept_merge"


def test_t61f6d8_rollout_plan_writes_decision_impact_plan_at_contract_path():
    """Verifies export plan creates plan at /app/output/decision_impact_plan.json with odip.plan.v1."""
    lattice = LATTICE_DEFAULT
    plan = Path("/app/output/decision_impact_plan.json")
    r = invoke_rollout(SCENARIO_ROOT / "dept_merge", lattice, plan)
    assert r.returncode == 0, r.stderr
    assert plan.is_file()
    body = json.loads(plan.read_text(encoding="utf-8"))
    assert body["schema_version"] == "odip.plan.v1"
    assert body["scenario_id"] == "dept_merge"


def test_t61f6d8_topology_fanout_rollout_units_match_fleet_reference():
    """Verifies topology fan-out affected_units match fleet rollout reference on dept_merge."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    assert invoke_rollout(SCENARIO_ROOT / "dept_merge", lattice, plan).returncode == 0
    lat = json.loads(lattice.read_text(encoding="utf-8"))
    ref = reference_fleet_rollout(SCENARIO_ROOT / "dept_merge")
    got = {r["decision_id"]: r for r in lat["impact_rows"]}
    for row in ref["impact_rows"]:
        assert got[row["decision_id"]]["affected_units"] == row["affected_units"]


def test_t61f6d8_fleet_resource_pool_contention_blocks_feasibility():
    """Verifies resource pool contention conflicts and feasible=false on dept_merge."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    assert invoke_rollout(SCENARIO_ROOT / "dept_merge", lattice, plan).returncode == 0
    body = json.loads(plan.read_text(encoding="utf-8"))
    ref = reference_fleet_rollout(SCENARIO_ROOT / "dept_merge")
    assert body["conflicts"] == ref["conflicts"]
    assert body["feasible"] is False


def test_t61f6d8_daemon_approval_sequence_includes_exception_board():
    """Verifies daemon approval sequence stacks exception_board for flagged decisions."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    assert invoke_rollout(SCENARIO_ROOT / "dept_merge", lattice, plan).returncode == 0
    body = json.loads(plan.read_text(encoding="utf-8"))
    ref = reference_fleet_rollout(SCENARIO_ROOT / "dept_merge")
    assert body["approval_steps"] == ref["approval_steps"]


def test_t61f6d8_topology_drift_timeline_conflicts_on_vendor_rollout():
    """Verifies topology drift timeline conflicts for exclusive overlapping vendor rollout."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    assert invoke_rollout(SCENARIO_ROOT / "vendor_replace", lattice, plan).returncode == 0
    body = json.loads(plan.read_text(encoding="utf-8"))
    ref = reference_fleet_rollout(SCENARIO_ROOT / "vendor_replace")
    assert body["conflicts"] == ref["conflicts"]
    assert any(c["type"] == "timeline" for c in body["conflicts"])


def test_t61f6d8_rollout_execution_order_lexicographic_kahn():
    """Verifies rollout execution_order follows lex-smallest Kahn ready pops."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    assert invoke_rollout(SCENARIO_ROOT / "vendor_replace", lattice, plan).returncode == 0
    body = json.loads(plan.read_text(encoding="utf-8"))
    ref = reference_fleet_rollout(SCENARIO_ROOT / "vendor_replace")
    assert body["execution_order"] == ref["execution_order"]


def test_t61f6d8_superseded_region_clearance_rejects_mismatched_token():
    """Verifies regulatory clearance rejection when region_expand token mismatches meta."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    assert invoke_rollout(SCENARIO_ROOT / "region_expand", lattice, plan).returncode == 0
    body = json.loads(plan.read_text(encoding="utf-8"))
    ref = reference_fleet_rollout(SCENARIO_ROOT / "region_expand")
    assert body["regulatory_blocks"] == ref["regulatory_blocks"]
    assert body["feasible"] is False


def test_t61f6d8_fleet_topology_child_attached_to_region_decision_r1():
    """Verifies decision R1 fan-out includes topology child U_APAC_SALES."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    assert invoke_rollout(SCENARIO_ROOT / "region_expand", lattice, plan).returncode == 0
    lat = json.loads(lattice.read_text(encoding="utf-8"))
    row = next(r for r in lat["impact_rows"] if r["decision_id"] == "R1")
    assert "U_APAC_SALES" in row["affected_units"]


def test_t61f6d8_rollout_score_gates_add_risk_and_board_roles():
    """Verifies impact_score gates add risk_committee and board_observer roles."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    assert invoke_rollout(SCENARIO_ROOT / "budget_realloc", lattice, plan).returncode == 0
    body = json.loads(plan.read_text(encoding="utf-8"))
    ref = reference_fleet_rollout(SCENARIO_ROOT / "budget_realloc")
    assert body["approval_steps"] == ref["approval_steps"]


def test_t61f6d8_fleet_flex_pool_overlap_emits_resource_conflict():
    """Verifies flex pool overlap emits resource conflict on budget_realloc."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    assert invoke_rollout(SCENARIO_ROOT / "budget_realloc", lattice, plan).returncode == 0
    body = json.loads(plan.read_text(encoding="utf-8"))
    ref = reference_fleet_rollout(SCENARIO_ROOT / "budget_realloc")
    assert body["conflicts"] == ref["conflicts"]


def test_t61f6d8_daemon_cycle_refusal_clears_rollout_order():
    """Verifies circular dependency refusal clears execution_order and feasible."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    assert invoke_rollout(SCENARIO_ROOT / "program_cancel", lattice, plan).returncode == 0
    body = json.loads(plan.read_text(encoding="utf-8"))
    ref = reference_fleet_rollout(SCENARIO_ROOT / "program_cancel")
    assert body["cycle_detected"] is True
    assert body["execution_order"] == []
    assert body["cycle_path"] == ref["cycle_path"]
    assert body["feasible"] is False


def test_t61f6d8_plan_reads_staged_fleet_snapshot_without_scenario_reopen():
    """Verifies plan uses staged fleet snapshot only; scenario dir may be absent."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    sc = SCENARIO_ROOT / "dept_merge"
    assert (
        subprocess.run(
            [
                ODIP_BIN,
                "stage",
                "--scenario",
                str(sc),
                "--policy",
                str(POLICY),
                "--out",
                str(lattice),
            ],
            cwd="/app",
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )
    parked = Path("/tmp/odip_scenario_park/dept_merge")
    parked.parent.mkdir(parents=True, exist_ok=True)
    if parked.exists():
        shutil.rmtree(parked)
    # shutil.move: fixtures and state may be on different Docker mounts
    shutil.move(str(sc), str(parked))
    try:
        r = subprocess.run(
            [
                ODIP_BIN,
                "plan",
                "--lattice",
                str(lattice),
                "--policy",
                str(POLICY),
                "--out",
                str(plan),
            ],
            cwd="/app",
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, r.stderr
        body = json.loads(plan.read_text(encoding="utf-8"))
        assert body["schema_version"] == "odip.plan.v1"
    finally:
        if parked.exists() and not sc.exists():
            shutil.move(str(parked), str(sc))


def test_t61f6d8_deterministic_rollout_digest_across_replay():
    """Verifies identical plan_digest on two fleet rollout replays with journal reset."""
    a_lat, a_plan = LATTICE_DEFAULT, PLAN_DEFAULT
    b_lat, b_plan = LATTICE_DEFAULT, PLAN_DEFAULT
    sc = SCENARIO_ROOT / "budget_realloc"
    assert invoke_rollout(sc, a_lat, a_plan).returncode == 0
    pa = json.loads(a_plan.read_text(encoding="utf-8"))
    if JOURNAL_DEFAULT.exists():
        JOURNAL_DEFAULT.unlink()
    assert invoke_rollout(sc, b_lat, b_plan).returncode == 0
    pb = json.loads(b_plan.read_text(encoding="utf-8"))
    assert pa["plan_digest"] == pb["plan_digest"]


def test_t61f6d8_lattice_digest_is_hex_witness_for_fleet_stage():
    """Verifies lattice_digest is 64-char hex witness after vendor stage."""
    lattice = LATTICE_DEFAULT
    assert (
        subprocess.run(
            [
                ODIP_BIN,
                "stage",
                "--scenario",
                str(SCENARIO_ROOT / "vendor_replace"),
                "--policy",
                str(POLICY),
                "--out",
                str(lattice),
            ],
            cwd="/app",
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )
    lat = json.loads(lattice.read_text(encoding="utf-8"))
    assert len(lat["lattice_digest"]) == 64
    int(lat["lattice_digest"], 16)  # lowercase hex witness


def test_t61f6d8_holdout_fleet_probe_conflicts_match_reference():
    """Verifies /opt/verifier-fixtures/odip-holdout conflicts and approvals match reference."""
    assert str(HOLD_ROOT).startswith("/opt/verifier-fixtures")
    if not HOLD_ROOT.is_dir():
        pytest.skip("holdout mount absent")
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    assert invoke_rollout(HOLD_ROOT, lattice, plan).returncode == 0
    body = json.loads(plan.read_text(encoding="utf-8"))
    ref = reference_fleet_rollout(HOLD_ROOT)
    assert body["conflicts"] == ref["conflicts"]
    assert body["approval_steps"] == ref["approval_steps"]
    assert body["scenario_id"] == "holdout_alpha"


def test_t61f6d8_holdout_h1_fanout_includes_hu3_and_keeps_clearance():
    """Verifies holdout decision H1 fans out to HU3 and is not clearance-blocked."""
    assert "/opt/verifier-fixtures" in str(HOLD_ROOT)
    if not HOLD_ROOT.is_dir():
        pytest.skip("holdout mount absent")
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    assert invoke_rollout(HOLD_ROOT, lattice, plan).returncode == 0
    lat = json.loads(lattice.read_text(encoding="utf-8"))
    body = json.loads(plan.read_text(encoding="utf-8"))
    row = next(r for r in lat["impact_rows"] if r["decision_id"] == "H1")
    assert "HU3" in row["affected_units"]
    assert not any(b["decision_id"] == "H1" for b in body["regulatory_blocks"])


def test_t61f6d8_default_paths_emit_impact_lattice_and_decision_impact_plan():
    """Verifies defaults write /app/state/odip/impact_lattice.json and /app/output/decision_impact_plan.json"""
    if LATTICE_DEFAULT.exists():
        LATTICE_DEFAULT.unlink()
    if PLAN_DEFAULT.exists():
        PLAN_DEFAULT.unlink()
    r = subprocess.run(
        [
            ODIP_BIN,
            "run",
            "--scenario",
            str(SCENARIO_ROOT / "dept_merge"),
            "--policy",
            str(POLICY),
        ],
        cwd="/app",
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    assert Path("/app/state/odip/impact_lattice.json").is_file()
    assert Path("/app/output/decision_impact_plan.json").is_file()


def test_t61f6d8_wrap_annotate_helper_present_for_rollout_emit():
    """Verifies wrap annotate helper source exists while rollout emit still succeeds."""
    assert (APP / "internal" / "wrap" / "wrap.go").is_file()
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    assert invoke_rollout(SCENARIO_ROOT / "dept_merge", lattice, plan).returncode == 0


def test_odip_epoch_seal_binds_lattice_digest_and_revision():
    """Verifies plan epoch_seal matches SHA-256 bind of lattice digest, epoch, scenario, revision."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    sc = SCENARIO_ROOT / "budget_realloc"
    assert invoke_rollout(sc, lattice, plan).returncode == 0
    lat = json.loads(lattice.read_text(encoding="utf-8"))
    body = json.loads(plan.read_text(encoding="utf-8"))
    ref = reference_fleet_rollout(sc)
    expect = _epoch_seal(
        lat["lattice_digest"],
        ref["rollout_epoch"],
        ref["scenario_id"],
        ref["topology_revision"],
    )
    assert body["epoch_seal"] == expect
    assert body["rollout_epoch"] == ref["rollout_epoch"]
    assert body["topology_revision"] == ref["topology_revision"]


def test_odip_rollout_journal_appends_after_plan_at_contract_path():
    """Verifies /app/state/odip/rollout_journal.jsonl gains a row after plan emit."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    sc = SCENARIO_ROOT / "vendor_replace"
    assert invoke_rollout(sc, lattice, plan).returncode == 0
    assert JOURNAL_DEFAULT.is_file()
    lines = [ln for ln in JOURNAL_DEFAULT.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert lines
    row = json.loads(lines[-1])
    body = json.loads(plan.read_text(encoding="utf-8"))
    assert row["scenario_id"] == "vendor_replace"
    assert row["plan_digest"] == body["plan_digest"]
    assert row["epoch_seal"] == body["epoch_seal"]


def test_odip_superseded_equal_epoch_refuses_second_plan_exit_4():
    """Verifies second plan for the same scenario epoch exits 4 without rewriting the plan digest."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    sc = SCENARIO_ROOT / "dept_merge"
    assert invoke_rollout(sc, lattice, plan).returncode == 0
    first = json.loads(plan.read_text(encoding="utf-8"))
    r2 = invoke_rollout(sc, lattice, plan)
    assert r2.returncode == 4, r2.stderr
    second = json.loads(plan.read_text(encoding="utf-8"))
    assert second["plan_digest"] == first["plan_digest"]


def test_odip_holdout_seal_fixture_epoch_seal_matches_reference():
    """Verifies /opt/verifier-fixtures/odip-holdout-seal epoch_seal matches independent reference."""
    if not HOLD_SEAL_ROOT.is_dir():
        pytest.skip("seal holdout mount absent")
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    assert invoke_rollout(HOLD_SEAL_ROOT, lattice, plan).returncode == 0
    lat = json.loads(lattice.read_text(encoding="utf-8"))
    body = json.loads(plan.read_text(encoding="utf-8"))
    ref = reference_fleet_rollout(HOLD_SEAL_ROOT)
    assert body["scenario_id"] == "holdout_seal"
    assert body["feasible"] is True
    expect = _epoch_seal(
        lat["lattice_digest"],
        ref["rollout_epoch"],
        ref["scenario_id"],
        ref["topology_revision"],
    )
    assert body["epoch_seal"] == expect
    assert body["bound_lattice_digest"] == lat["lattice_digest"]


def test_odip_export_bound_lattice_digest_matches_staged_witness():
    """Verifies bound_lattice_digest on decision_impact_plan equals staged lattice_digest."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    assert invoke_rollout(SCENARIO_ROOT / "region_expand", lattice, plan).returncode == 0
    lat = json.loads(lattice.read_text(encoding="utf-8"))
    body = json.loads(plan.read_text(encoding="utf-8"))
    assert body["bound_lattice_digest"] == lat["lattice_digest"]
    assert Path("/app/output/decision_impact_plan.json").is_file()


def test_odip_window_digest_binds_exclusive_decision_windows():
    """Verifies plan window_digest matches SHA-256 of sorted exclusive window lines."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    sc = SCENARIO_ROOT / "budget_realloc"
    assert invoke_rollout(sc, lattice, plan).returncode == 0
    body = json.loads(plan.read_text(encoding="utf-8"))
    ref = reference_fleet_rollout(sc)
    assert body["window_digest"] == ref["window_digest"]


def test_odip_booking_digest_binds_resource_intervals():
    """Verifies plan booking_digest matches SHA-256 of sorted pool booking lines."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    sc = SCENARIO_ROOT / "vendor_replace"
    assert invoke_rollout(sc, lattice, plan).returncode == 0
    body = json.loads(plan.read_text(encoding="utf-8"))
    ref = reference_fleet_rollout(sc)
    assert body["booking_digest"] == ref["booking_digest"]


def test_odip_journal_carries_window_and_booking_digests():
    """Verifies journal row copies window_digest and booking_digest from the plan."""
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    sc = SCENARIO_ROOT / "budget_realloc"
    assert invoke_rollout(sc, lattice, plan).returncode == 0
    body = json.loads(plan.read_text(encoding="utf-8"))
    lines = [ln for ln in JOURNAL_DEFAULT.read_text(encoding="utf-8").splitlines() if ln.strip()]
    row = json.loads(lines[-1])
    assert row["window_digest"] == body["window_digest"]
    assert row["booking_digest"] == body["booking_digest"]


def test_odip_holdout_slot_digests_match_reference():
    """Verifies /opt/verifier-fixtures/odip-holdout-slot digests match independent reference."""
    if not HOLD_SLOT_ROOT.is_dir():
        pytest.skip("slot holdout mount absent")
    lattice = LATTICE_DEFAULT
    plan = PLAN_DEFAULT
    assert invoke_rollout(HOLD_SLOT_ROOT, lattice, plan).returncode == 0
    body = json.loads(plan.read_text(encoding="utf-8"))
    ref = reference_fleet_rollout(HOLD_SLOT_ROOT)
    assert body["scenario_id"] == "holdout_slot"
    assert body["feasible"] is True
    assert body["window_digest"] == ref["window_digest"]
    assert body["booking_digest"] == ref["booking_digest"]

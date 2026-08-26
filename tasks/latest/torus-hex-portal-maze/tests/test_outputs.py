"""Verifier for torus hex portal ladder replay repair."""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
SEAL = Path("/opt/task-seal/environment")
MANIFEST = Path("/opt/task-seal/manifest.json")
REPORT = Path("/app/output/ladder_replay_report.json")
MAPS = SEAL / "fixtures/maps"
SUITE = MAPS / "ladder_suite.json"
ROW_KEYS = {
    "seed_id",
    "path_stamp",
    "tick_total",
    "cost_total",
    "wrap_events",
    "portal_hops",
    "replay_digest",
}
POINTY_Q = [1, 1, 0, -1, -1, 0]
POINTY_R = [0, -1, -1, 0, 1, 1]
FLAT_Q = [1, 0, -1, -1, 0, 1]
FLAT_R = [0, -1, -1, 0, 1, 1]


def _load_graded():
    doc = json.loads(SUITE.read_text())
    return sorted(doc["graded"])


GRADED = _load_graded()


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _verify_fixture_integrity() -> None:
    manifest = json.loads(MANIFEST.read_text())
    for rel, expected in manifest.items():
        path = ENV / rel
        assert path.is_file(), f"missing protected fixture: {rel}"
        actual = _sha256_hex(path.read_bytes())
        assert actual == expected, f"tampered protected fixture: {rel}"


def _deltas(orient: str):
    if orient == "flat":
        return FLAT_Q, FLAT_R
    return POINTY_Q, POINTY_R


def _wrap(q, r, w, h):
    return q % w, r % h


def _gate(pos, links, step_dir):
    for link in links:
        fr = tuple(link["from"])
        to = tuple(link["to"])
        arms = link.get("arms", list(range(6)))
        if pos == fr and step_dir in arms:
            return to
    return None


def _terrain(q, r, table):
    return table.get(f"{q},{r}", 1)


def _simulate(spec):
    steps = list(spec["steps"])
    orient = spec.get("orient", "pointy")
    dq, dr = _deltas(orient)
    wet_window = int(spec.get("wet_window", 0))
    q, r = spec["start"]
    path = [(q, r)]
    ticks = []
    cost_total = 0
    wrap_events = 0
    portal_hops = 0
    wet_left = 0
    w, h = spec["width"], spec["height"]
    for idx, d in enumerate(steps):
        d = d % 6
        raw_q, raw_r = q + dq[d], r + dr[d]
        before = (raw_q, raw_r)
        q, r = _wrap(raw_q, raw_r, w, h)
        did_wrap = (q, r) != before
        if did_wrap:
            wrap_events += 1
            wet_left = wet_window
        via = False
        dest = _gate((q, r), spec.get("portals", []), d)
        if dest:
            q, r = dest
            via = True
            portal_hops += 1
        tc = _terrain(q, r, spec["terrain"])
        if wet_left > 0 and not via:
            tc *= 2
            wet_left -= 1
        if not via:
            cost_total += tc
        path.append((q, r))
        ticks.append(
            {
                "tick": idx + 1,
                "q": q,
                "r": r,
                "step_cost": tc,
                "via_portal": via,
            }
        )
    return {
        "path": path,
        "ticks": ticks,
        "cost_total": cost_total,
        "wrap_events": wrap_events,
        "portal_hops": portal_hops,
    }


def _contract_row(spec):
    sim = _simulate(spec)
    stamp_src = ";".join(f"{a},{b}" for a, b in sim["path"])
    path_stamp = _sha256_hex(stamp_src.encode())[:8]
    replay_digest = _sha256_hex(
        json.dumps(sim["ticks"], separators=(",", ":")).encode()
    )
    return {
        "seed_id": spec["seed_id"],
        "path_stamp": path_stamp,
        "tick_total": len(sim["ticks"]),
        "cost_total": sim["cost_total"],
        "wrap_events": sim["wrap_events"],
        "portal_hops": sim["portal_hops"],
        "replay_digest": replay_digest,
    }


def _expected_rows():
    rows = {}
    for seed in GRADED:
        spec = json.loads((MAPS / f"{seed}.json").read_text())
        rows[seed] = _contract_row(spec)
    return rows


def _rebuild_and_grade():
    _verify_fixture_integrity()
    if REPORT.exists():
        REPORT.unlink()
    subprocess.run(["bash", str(ENV / "scripts/build_all.sh")], check=True, cwd="/app")
    subprocess.run(["bash", str(ENV / "scripts/run_ladder.sh")], check=True, cwd="/app")
    assert REPORT.exists(), "expected graded ladder replay report"
    return json.loads(REPORT.read_text())


@pytest.fixture(scope="module")
def payload():
    return _rebuild_and_grade()


@pytest.fixture(scope="module")
def expected():
    return _expected_rows()


def rows_by_seed(report):
    return {row["seed_id"]: row for row in report["rows"]}


def test_k0():
    """Protected fixtures and docs match the read-only fixture seal manifest."""
    _verify_fixture_integrity()


def test_k1(payload):
    """Report exposes the graded contract schema for every suite seed."""
    assert set(payload.keys()) == {"rows"}
    names = [row["seed_id"] for row in payload["rows"]]
    assert names == sorted(names)
    assert set(names) == set(GRADED)
    for row in payload["rows"]:
        assert set(row.keys()) == ROW_KEYS
        assert len(row["path_stamp"]) == 8
        assert len(row["replay_digest"]) == 64


def test_k2(payload, expected):
    """Public pointy sample stays stable under rebuild."""
    seed = "moss_trail"
    row = rows_by_seed(payload)[seed]
    exp = expected[seed]
    assert row["cost_total"] == exp["cost_total"]
    assert row["path_stamp"] == exp["path_stamp"]
    assert row["portal_hops"] == 0


def test_k3(payload, expected):
    """Flat orientation boards use flat neighbor deltas."""
    seed = "flat_ridge"
    row = rows_by_seed(payload)[seed]
    exp = expected[seed]
    assert row["path_stamp"] == exp["path_stamp"]
    assert row["replay_digest"] == exp["replay_digest"]
    assert row["cost_total"] == exp["cost_total"]


def test_k4(payload, expected):
    """Negative-edge remapping lands on the far rim."""
    seed = "neg_wrap"
    row = rows_by_seed(payload)[seed]
    exp = expected[seed]
    assert row["wrap_events"] == exp["wrap_events"]
    assert row["wrap_events"] >= 2
    assert row["path_stamp"] == exp["path_stamp"]


def test_k5(payload, expected):
    """Portal arms allow only listed entry bearings."""
    seed = "portal_arm"
    row = rows_by_seed(payload)[seed]
    exp = expected[seed]
    assert row["portal_hops"] == 1
    assert row["cost_total"] == exp["cost_total"]
    assert row["path_stamp"] == exp["path_stamp"]


def test_k6(payload, expected):
    """Illegal portal bearings must not teleport."""
    seed = "portal_deny"
    row = rows_by_seed(payload)[seed]
    exp = expected[seed]
    assert row["portal_hops"] == 0
    assert row["path_stamp"] == exp["path_stamp"]
    assert row["replay_digest"] == exp["replay_digest"]


def test_k7(payload, expected):
    """Wet rim doubles terrain after edge remaps."""
    seed = "wet_rim"
    row = rows_by_seed(payload)[seed]
    exp = expected[seed]
    assert row["wrap_events"] >= 1
    assert row["cost_total"] == exp["cost_total"]
    assert row["cost_total"] > 3
    assert row["replay_digest"] == exp["replay_digest"]


def test_k8(payload, expected):
    """Same-tick portal chains must not fire."""
    seed = "chain_trap"
    row = rows_by_seed(payload)[seed]
    exp = expected[seed]
    assert row["portal_hops"] == 1
    assert row["path_stamp"] == exp["path_stamp"]
    assert row["cost_total"] == exp["cost_total"]


def test_k9(payload, expected):
    """Wrap-then-portal with matching arms reaches the landing cell."""
    seed = "wrap_portal"
    row = rows_by_seed(payload)[seed]
    exp = expected[seed]
    assert row["wrap_events"] == 1
    assert row["portal_hops"] == 1
    assert row["cost_total"] == exp["cost_total"]
    assert row["path_stamp"] == exp["path_stamp"]


def test_k10(payload, expected):
    """Flat wrap, wet, and armed portal must coordinate on combo packs."""
    seed = "combo_hard"
    row = rows_by_seed(payload)[seed]
    exp = expected[seed]
    assert row["wrap_events"] == exp["wrap_events"]
    assert row["portal_hops"] == exp["portal_hops"]
    assert row["cost_total"] == exp["cost_total"]
    assert row["replay_digest"] == exp["replay_digest"]


def test_k11(payload, expected):
    """Every graded row matches derived contract metrics end-to-end."""
    got = rows_by_seed(payload)
    for seed in GRADED:
        for key in ROW_KEYS:
            assert got[seed][key] == expected[seed][key]


def test_k12(payload):
    """Back-to-back rebuild and ladder runs reproduce identical report bytes."""
    first = json.loads(json.dumps(payload))
    second = _rebuild_and_grade()
    assert second == first

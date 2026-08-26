"""Verifier for haproxy-acl-backend-route-matrix-composer (v2 hard set)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

OUT = Path("/app/output/haproxy_route_audit.json")
ENV = Path("/app/environment")
FIXTURES = ENV / "fixtures" / "qv"
SESSION = ENV / "state" / "session.registry"
JOURNAL = ENV / "state" / "journal"
LEDGER = ENV / "state" / "ledger.jsonl"
GENERATIONS = ENV / "state" / "generations"
CURRENT = ENV / "state" / "current"
TXNS = ENV / "state" / "txns"
QUARANTINE = ENV / "state" / "quarantine"
SHADOW = Path("/app/var/qxhub/lane.shadow")
PLANS = Path("/app/var/qxhub/plans")
DRV = ENV / "bin" / "lb_drive"

ARM_FILES = {
    "dense": "t0.json",
    "sparse": "t1.json",
    "weave": "t2.json",
    "starve": "t3.json",
    "held_out": "t4.json",
    "side_cut": "t5.json",
    "side_rcv": "t6.json",
    "side_prt": "t7.json",
    "side_stl": "t8.json",
}

BASELINE = {"active_gen": 3, "floor": 2, "anchor": "32", "epoch": 1, "last_arm": ""}


def _reset() -> None:
    OUT.unlink(missing_ok=True)
    LEDGER.unlink(missing_ok=True)
    CURRENT.unlink(missing_ok=True)
    for d in (GENERATIONS, TXNS, QUARANTINE):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)
    JOURNAL.mkdir(parents=True, exist_ok=True)
    for p in JOURNAL.glob("*.jnl"):
        p.unlink()
    SHADOW.unlink(missing_ok=True)
    if PLANS.exists():
        for p in PLANS.iterdir():
            if p.is_file():
                p.unlink()
    SESSION.write_text(json.dumps(BASELINE, indent=2) + "\n", encoding="utf-8")


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [str(DRV), *args]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if check and proc.returncode != 0:
        raise AssertionError(
            f"failed: lb_drive {' '.join(args)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def drive(arm: str) -> dict:
    OUT.unlink(missing_ok=True)
    _run(["--arm", arm, "--out", str(OUT)])
    assert OUT.is_file(), f"missing regenerated output {OUT}"
    return json.loads(OUT.read_text(encoding="utf-8"))


def fixture(arm: str) -> dict:
    return json.loads((FIXTURES / ARM_FILES[arm]).read_text(encoding="utf-8"))


def session() -> dict:
    return json.loads(SESSION.read_text(encoding="utf-8"))


def seal_anchor(gen: int, floor: int, epoch: int) -> str:
    return format(gen * 13 + floor * 5 + epoch, "x")


def sha256_hex(data: bytes) -> str:
    proc = subprocess.run(["sha256sum"], input=data, capture_output=True, check=True)
    return proc.stdout.split()[0].decode()


def ledger_entries() -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        out.append(json.loads(line))
    return out


def assert_chain(entries: list[dict]) -> None:
    prev = "0"
    for e in entries:
        assert e["prev"] == prev, f"chain break at gen {e['gen']}: prev={e['prev']}"
        payload = f"{e['prev']}|{e['gen']}|{e['arm']}|{e['seal']}|{e['tx']}"
        assert e["hash"] == sha256_hex(payload.encode()), f"hash mismatch at gen {e['gen']}"
        prev = e["hash"]


def manifest_recomputes(gen: int) -> str:
    d = GENERATIONS / str(gen)
    raw = (d / "manifest.json").read_bytes()
    seal = (d / "MSEAL").read_text(encoding="utf-8").strip()
    assert sha256_hex(raw) == seal, f"generation {gen} seal does not recompute"
    doc = json.loads(raw)
    assert doc["generation"] == gen
    return seal


def row_match(row: dict) -> list:
    return row.get("Match") or row.get("match") or []


def rows_sans_seq(audit: dict) -> list[dict]:
    return [{k: v for k, v in row.items() if k != "Seq"} for row in audit["rule_rows"]]


def derived_rows(fx: dict) -> list[tuple]:
    """Expected (kind, mode, target, matchers) tuples: never rows first."""
    never = sorted(
        ("never", c["kind"], "", (c["match"],))
        for c in fx["cells"]
        if c["want"] == "deny"
    )
    packs: dict[tuple, list] = {}
    for c in fx["cells"]:
        if c["want"] != "route":
            continue
        packs.setdefault((c["kind"], c["target"]), []).append(c["match"])
    always = [
        ("always", kind, target, tuple(sorted(matchers)))
        for (kind, target), matchers in sorted(packs.items())
    ]
    out = [(k, m, t, tuple(ms)) for (m, k, t, ms) in never]
    out += [(k, m, t, ms) for (m, k, t, ms) in always]
    return out


def derived_outcome(rows: list[dict], cell: dict) -> tuple:
    """First-match simulation over emitted rule_rows with verbatim matchers."""
    for row in rows:
        if row["Kind"] != cell["kind"]:
            continue
        if cell["match"] not in row_match(row):
            continue
        if row["Mode"] == "never":
            return ("deny", "", "")
        return ("hit", row["Target"], row["Group"])
    return ("miss", "", "")


def assert_plan(audit: dict, fx: dict) -> None:
    rows = audit["rule_rows"]
    got_shape = [(r["Kind"], r["Mode"], r["Target"], tuple(row_match(r))) for r in rows]
    want_shape = list(derived_rows(fx))
    assert got_shape == want_shape, f"rule_rows shape mismatch:\n{got_shape}\n{want_shape}"
    assert len(rows) <= audit["expected_row_cap"] == fx["row_cap"]
    assert audit["route_count"] == len(rows)

    outcomes = {o["id"]: o for o in audit["cell_outcomes"]}
    assert sorted(outcomes) == sorted(c["id"] for c in fx["cells"])
    for cell in fx["cells"]:
        want = ("hit", cell["target"]) if cell["want"] == "route" else ("deny", "")
        o = outcomes[cell["id"]]
        d_out, d_target, d_group = derived_outcome(rows, cell)
        assert (o["outcome"], o["target"]) == want, f"{cell['id']}: {o}"
        assert (o["outcome"], o["target"], o["group"]) == (d_out, d_target, d_group)
        if cell["want"] == "deny":
            assert o["group"] == ""
        else:
            assert o["group"] != ""


def assert_groups(audit: dict, fx: dict) -> None:
    rows = audit["rule_rows"]
    groups = audit["group_keys"]
    assert groups == sorted(set(groups))
    assert len(groups) <= audit["expected_group_cap"] == fx["group_cap"]
    assert audit["group_count"] == len(groups)
    pair_to_group: dict[tuple, str] = {}
    for r in rows:
        if r["Mode"] == "never":
            assert r["Group"] == "" and r["Key"] == ""
            continue
        assert r["Group"] != ""
        pair = (r["Kind"], r["Target"])
        assert pair not in pair_to_group
        pair_to_group[pair] = r["Group"]
    assert sorted(set(pair_to_group.values())) == groups
    assert len(set(pair_to_group.values())) == len(pair_to_group)


def assert_seals(audit: dict) -> None:
    pane = audit["pane_digest"]
    assert isinstance(pane, str) and len(pane) == 64
    assert pane == audit["twin_digest"]
    stamp_text = f"{audit['arm']}:{pane}:{audit['session_floor']}:{audit['session_gen']}\n"
    assert audit["run_stamp"] == sha256_hex(stamp_text.encode())


def assert_hops(audit: dict, fx: dict) -> None:
    routed = sorted(c["id"] for c in fx["cells"] if c["want"] == "route")
    matchers = {c["match"] for c in fx["cells"]}
    hop_ids = [h["id"] for h in audit["hop_records"]]
    assert hop_ids == routed
    assert not (set(hop_ids) & matchers)
    outcomes = {o["id"]: o for o in audit["cell_outcomes"]}
    for h in audit["hop_records"]:
        assert h["cover"] == "always"
        assert h["group"] == outcomes[h["id"]]["group"]
        assert h["group"] in audit["group_keys"]


@pytest.fixture(scope="session", autouse=True)
def rebuild() -> None:
    subprocess.run(["bash", str(ENV / "scripts" / "build_all.sh")], check=True)
    data = DRV.read_bytes()
    assert data[:4] == b"\x7fELF", "lb_drive must be an ELF binary"
    assert not data.startswith(b"#!"), "lb_drive must not be a script"
    probe_cmd = ["go", "version", "-m", str(DRV)]
    probe = subprocess.run(probe_cmd, capture_output=True, text=True, check=False)
    assert probe.returncode == 0, probe.stderr
    assert "qxhub" in probe.stdout


def test_hrx_v2_h01_schema_generation_ledger_bootstrap() -> None:
    """dense bootstrap: schema, generation seal, ledger hash, and counters agree."""
    _reset()
    audit = drive("dense")
    for key in (
        "arm",
        "rule_rows",
        "route_count",
        "group_count",
        "cell_outcomes",
        "group_keys",
        "hop_records",
        "pane_digest",
        "twin_digest",
        "expected_row_cap",
        "expected_group_cap",
        "session_floor",
        "session_gen",
        "interrupt",
        "run_stamp",
        "generation",
        "manifest_seal",
        "ledger_head",
        "plan_token",
        "status",
    ):
        assert key in audit, f"missing audit field {key}"
    assert audit["arm"] == "dense"
    assert audit["interrupt"] is False and audit["status"] == "ok"
    assert audit["route_count"] == len(audit["rule_rows"]) > 0
    assert_seals(audit)
    sess = session()
    assert (sess["active_gen"], sess["floor"], sess["epoch"]) == (4, 3, 2)
    assert sess["anchor"] == seal_anchor(4, 3, 2)
    assert audit["session_gen"] == 4 and audit["session_floor"] == 3
    assert audit["generation"] == 4
    assert CURRENT.read_text(encoding="utf-8").strip() == "4"
    seal = manifest_recomputes(4)
    assert audit["manifest_seal"] == seal
    ents = ledger_entries()
    assert len(ents) == 1
    assert_chain(ents)
    e = ents[0]
    assert (e["gen"], e["floor"], e["epoch"], e["arm"], e["seal"]) == (4, 3, 2, "dense", seal)
    assert audit["ledger_head"] == e["hash"]


def test_hrx_v2_h02_dense_plan_groups_hops_chain() -> None:
    """dense plan, group bijection, and hop records hold across chained reruns."""
    _reset()
    fx = fixture("dense")
    a1 = drive("dense")
    assert_plan(a1, fx)
    assert_groups(a1, fx)
    assert_hops(a1, fx)
    a2 = drive("dense")
    assert rows_sans_seq(a1) == rows_sans_seq(a2)
    assert a1["cell_outcomes"] == a2["cell_outcomes"]
    assert a1["pane_digest"] == a2["pane_digest"]
    assert a2["generation"] == a1["generation"] + 1
    ents = ledger_entries()
    assert len(ents) == 2
    manifest_recomputes(a1["generation"])
    manifest_recomputes(a2["generation"])


def test_hrx_v2_h03_sparse_verbatim_weave_deny_segregation() -> None:
    """sparse verbatim nesting and weave deny-first segregation across arms."""
    _reset()
    fx_s = fixture("sparse")
    a_s = drive("sparse")
    assert_plan(a_s, fx_s)
    outcomes = {o["id"]: o for o in a_s["cell_outcomes"]}
    assert outcomes["s06"]["target"] == "be_apex"
    assert outcomes["s03"]["target"] == "be_beta"
    assert outcomes["s06"]["group"] != outcomes["s03"]["group"]

    fx_w = fixture("weave")
    a_w = drive("weave")
    assert_plan(a_w, fx_w)
    assert_groups(a_w, fx_w)
    modes = [r["Mode"] for r in a_w["rule_rows"]]
    assert modes == sorted(modes, key=lambda m: 0 if m == "never" else 1)
    outcomes = {o["id"]: o for o in a_w["cell_outcomes"]}
    assert outcomes["w05"]["outcome"] == "deny" and outcomes["w06"]["outcome"] == "deny"
    assert outcomes["w07"]["target"] == "be_deep"
    host_groups = {
        outcomes[c["id"]]["group"]
        for c in fx_w["cells"]
        if c["kind"] == "host" and c["want"] == "route"
    }
    path_groups = {
        outcomes[c["id"]]["group"]
        for c in fx_w["cells"]
        if c["kind"] == "path" and c["want"] == "route"
    }
    assert host_groups and path_groups and not (host_groups & path_groups)

    assert a_w["session_gen"] == a_s["session_gen"] + 1
    ents = ledger_entries()
    assert [e["arm"] for e in ents] == ["sparse", "weave"]


def test_hrx_v2_h04_starve_exact_ceiling_verify_ok() -> None:
    """starve packs to the exact group ceiling and verify stays consistent."""
    _reset()
    fx = fixture("starve")
    audit = drive("starve")
    assert_plan(audit, fx)
    assert_groups(audit, fx)
    assert len(audit["group_keys"]) == fx["group_cap"]
    vf = json.loads(_run(["verify"]).stdout)
    assert vf.get("ok") is True, vf
    assert int(vf["active_gen"]) == audit["session_gen"]
    assert int(vf["current"]) == audit["generation"]


def test_hrx_v2_h05_held_out_digests_manifest_recompute() -> None:
    """held_out digests reproduce across runs; both manifests reseal independently."""
    _reset()
    fx = fixture("held_out")
    a1 = drive("held_out")
    assert_plan(a1, fx)
    assert_seals(a1)
    a2 = drive("held_out")
    assert a2["pane_digest"] == a1["pane_digest"]
    assert a2["twin_digest"] == a1["twin_digest"]
    assert rows_sans_seq(a2) == rows_sans_seq(a1)
    assert_seals(a2)
    s1 = manifest_recomputes(a1["generation"])
    s2 = manifest_recomputes(a2["generation"])
    assert a1["manifest_seal"] == s1 and a2["manifest_seal"] == s2
    ents = ledger_entries()
    assert len(ents) == 2
    assert_chain(ents)
    assert ents[0]["seal"] != ents[1]["seal"]  # generation number is sealed inside


def test_hrx_v2_h06_stale_plan_commit_rejected() -> None:
    """a plan token goes stale once the session advances; commit must not land."""
    _reset()
    PLANS.mkdir(parents=True, exist_ok=True)
    plan_path = PLANS / "dense_plan.json"
    tok = _run(["plan", "--arm", "dense", "--out", str(plan_path)]).stdout.strip()
    assert tok and plan_path.is_file()
    drive("sparse")
    ledger_before = LEDGER.read_text(encoding="utf-8")
    current_before = CURRENT.read_text(encoding="utf-8")
    sess_before = session()
    gens_before = sorted(p.name for p in GENERATIONS.iterdir())
    bad = _run(
        ["commit", "--plan", str(plan_path), "--cas", tok, "--out", str(OUT)],
        check=False,
    )
    assert bad.returncode != 0, "stale commit must fail"
    assert LEDGER.read_text(encoding="utf-8") == ledger_before
    assert CURRENT.read_text(encoding="utf-8") == current_before
    assert session() == sess_before
    assert sorted(p.name for p in GENERATIONS.iterdir()) == gens_before


def test_hrx_v2_h07_registry_loss_replay_from_ledger() -> None:
    """replay rebuilds registry and current from the ledger, floor lag included."""
    _reset()
    drive("dense")
    audit = drive("weave")
    ents = ledger_entries()
    assert len(ents) == 2
    last = ents[-1]
    SESSION.unlink()
    CURRENT.unlink()
    _run(["replay"])
    sess = session()
    assert sess["active_gen"] == last["gen"] == audit["session_gen"]
    assert sess["floor"] == last["floor"] == audit["session_floor"]
    assert sess["epoch"] == last["epoch"]
    assert sess["floor"] < sess["active_gen"]
    assert sess["anchor"] == seal_anchor(sess["active_gen"], sess["floor"], sess["epoch"])
    assert sess["last_arm"] == "weave"
    assert CURRENT.read_text(encoding="utf-8").strip() == str(last["gen"])
    st = json.loads(_run(["status"]).stdout)
    assert int(st["active_gen"]) == last["gen"]
    assert int(st["floor"]) == last["floor"]
    assert st["ledger_head"] == last["hash"]


def test_hrx_v2_h08_corrupt_manifest_quarantined_fallback() -> None:
    """a corrupt latest manifest is quarantined; recover reports the intact one."""
    _reset()
    a1 = drive("dense")
    g1 = a1["generation"]
    seal1 = manifest_recomputes(g1)
    a2 = drive("sparse")
    g2 = a2["generation"]
    assert g2 > g1
    (GENERATIONS / str(g2) / "manifest.json").write_text(
        '{"generation":999,"arm":"forged","pane":"","groups":[],"rows":[]}\n',
        encoding="utf-8",
    )
    out = _run(["recover"])
    parts = out.stdout.strip().split()
    assert len(parts) == 2, out.stdout
    assert int(parts[0]) == g1
    assert parts[1] == seal1
    assert CURRENT.read_text(encoding="utf-8").strip() == str(g1)
    assert not (GENERATIONS / str(g2)).exists(), "corrupt generation left in place"
    assert any(QUARANTINE.iterdir()), "nothing quarantined"
    manifest_recomputes(g1)


def test_hrx_v2_h09_idempotent_commit_no_duplicates() -> None:
    """re-committing a recorded transaction re-emits without new ledger rows."""
    _reset()
    PLANS.mkdir(parents=True, exist_ok=True)
    plan_path = PLANS / "held_out_plan.json"
    tok = _run(["plan", "--arm", "held_out", "--out", str(plan_path)]).stdout.strip()
    _run(["commit", "--plan", str(plan_path), "--cas", tok, "--out", str(OUT)])
    ents1 = ledger_entries()
    assert len(ents1) == 1
    gens1 = sorted(p.name for p in GENERATIONS.iterdir())
    current1 = CURRENT.read_text(encoding="utf-8")
    sess1 = session()
    again = _run(["commit", "--plan", str(plan_path), "--cas", tok, "--out", str(OUT)])
    assert again.returncode == 0
    audit = json.loads(OUT.read_text(encoding="utf-8"))
    assert audit["route_count"] > 0
    ents2 = ledger_entries()
    assert len(ents2) == 1
    assert ents2[0]["tx"] == ents1[0]["tx"]
    assert sorted(p.name for p in GENERATIONS.iterdir()) == gens1
    assert CURRENT.read_text(encoding="utf-8") == current1
    assert session() == sess1


def test_hrx_v2_h10_cut_journals_empty_sealed_rows() -> None:
    """side_cut journals under the fixed name and seals no inventory at all."""
    _reset()
    before = session()
    fx = fixture("side_cut")
    audit = drive("side_cut")
    assert audit["interrupt"] is True
    assert audit["status"] == "interrupted"
    assert audit["rule_rows"] == [] and audit["route_count"] == 0
    assert audit["cell_outcomes"] == [] and audit["hop_records"] == []
    assert audit["group_keys"] == [] and audit["group_count"] == 0
    assert audit["generation"] == 0 and audit["manifest_seal"] == ""
    assert isinstance(audit["pane_digest"], str) and len(audit["pane_digest"]) == 64
    after = session()
    assert after["active_gen"] == before["active_gen"] + 1
    assert after["floor"] == before["floor"]
    assert after["epoch"] == before["epoch"]
    assert after["anchor"] == seal_anchor(
        after["active_gen"], after["floor"], after["epoch"]
    )
    jnl = JOURNAL / "cut.jnl"
    assert jnl.is_file(), "cut journal missing under fixed name cut.jnl"
    assert not (JOURNAL / (fx["arm"] + ".jnl")).exists()
    entry = json.loads(jnl.read_text(encoding="utf-8"))
    assert entry["arm"] == "side_cut"
    assert entry["pending"] == len(derived_rows(fx))
    assert ledger_entries() == []
    assert sorted(p.name for p in GENERATIONS.iterdir()) == []


def test_hrx_v2_h11_cut_torn_ledger_recover_exactly_once() -> None:
    """recover consumes journal and shadow across a torn ledger tail, exactly once."""
    _reset()
    drive("dense")
    drive("side_cut")
    assert (JOURNAL / "cut.jnl").is_file()
    with LEDGER.open("ab") as fh:
        fh.write(b'{"prev":"0","gen":')
    SHADOW.parent.mkdir(parents=True, exist_ok=True)
    SHADOW.write_text(
        json.dumps({"kind": "host", "match": "cuta.lab", "target": "be_cut"}) + "\n",
        encoding="utf-8",
    )
    fx = fixture("side_rcv")
    audit = drive("side_rcv")
    assert audit["interrupt"] is False
    assert_plan(audit, fx)
    assert sorted(p.name for p in JOURNAL.glob("*.jnl")) == []
    assert not SHADOW.exists(), "recover left the lane shadow behind"
    cut_matchers = {c["match"] for c in fixture("side_cut")["cells"]}
    for row in audit["rule_rows"]:
        assert not (set(row_match(row)) & cut_matchers), "cut rows resurrected"
    ents = ledger_entries()
    assert [e["arm"] for e in ents] == ["dense", "side_rcv"]
    assert_chain(ents)
    raw_lines = [ln for ln in LEDGER.read_text(encoding="utf-8").splitlines() if ln.strip()]
    for ln in raw_lines:
        json.loads(ln)  # torn tail must be gone
    sess = session()
    assert (sess["active_gen"], sess["floor"], sess["epoch"]) == (6, 5, 3)
    assert audit["session_gen"] == 6 and audit["session_floor"] == 5


def test_hrx_v2_h12_partial_stale_floor_lag_shadow_rejection() -> None:
    """partial keeps the floor lag through status; stale never folds the shadow."""
    _reset()
    fx_p = fixture("side_prt")
    a_p = drive("side_prt")
    assert_plan(a_p, fx_p)
    sess = session()
    assert (sess["active_gen"], sess["floor"], sess["epoch"]) == (4, 2, 2)
    assert a_p["session_floor"] < a_p["session_gen"]
    st = json.loads(_run(["status"]).stdout)
    assert int(st["floor"]) < int(st["active_gen"])
    assert st["anchor"] == seal_anchor(int(st["active_gen"]), int(st["floor"]), int(st["epoch"]))

    SHADOW.parent.mkdir(parents=True, exist_ok=True)
    SHADOW.write_text(
        json.dumps({"kind": "host", "match": "ghost.lab", "target": "be_wrong"}) + "\n",
        encoding="utf-8",
    )
    try:
        fx_s = fixture("side_stl")
        a_s = drive("side_stl")
        assert_plan(a_s, fx_s)
        for row in a_s["rule_rows"]:
            assert row["Target"] != "be_wrong"
            if row["Mode"] == "always":
                assert "ghost.lab" not in row_match(row)
        outcomes = {o["id"]: o for o in a_s["cell_outcomes"]}
        assert outcomes["x03"]["outcome"] == "deny"
        assert_seals(a_s)
        sess = session()
        assert (sess["active_gen"], sess["floor"], sess["epoch"]) == (5, 3, 3)
        vf = json.loads(_run(["verify"]).stdout)
        assert vf.get("ok") is True, vf
    finally:
        SHADOW.unlink(missing_ok=True)


def test_hrx_v2_h13_forged_overwrite_cross_consistency() -> None:
    """forged audits are regenerated; status, verify, ledger, and audit agree."""
    _reset()
    a1 = drive("held_out")
    forged = {
        "arm": "held_out",
        "rule_rows": [],
        "route_count": 0,
        "group_count": 0,
        "cell_outcomes": [],
        "group_keys": [],
        "hop_records": [],
        "pane_digest": "0" * 64,
        "twin_digest": "0" * 64,
        "expected_row_cap": 0,
        "expected_group_cap": 0,
        "session_floor": 0,
        "session_gen": 0,
        "interrupt": False,
        "run_stamp": "0" * 64,
        "generation": 0,
        "manifest_seal": "",
        "ledger_head": "",
        "plan_token": "",
        "status": "ok",
    }
    OUT.write_text(json.dumps(forged) + "\n", encoding="utf-8")
    fx = fixture("held_out")
    a2 = drive("held_out")
    assert a2["pane_digest"] == a1["pane_digest"] != "0" * 64
    assert_plan(a2, fx)
    assert_groups(a2, fx)
    assert_hops(a2, fx)
    assert_seals(a2)
    sess = session()
    assert sess["anchor"] == seal_anchor(sess["active_gen"], sess["floor"], sess["epoch"])
    assert a2["session_gen"] == sess["active_gen"]
    assert a2["session_floor"] == sess["floor"]
    st = json.loads(_run(["status"]).stdout)
    vf = json.loads(_run(["verify"]).stdout)
    assert vf.get("ok") is True, vf
    assert st["ledger_head"] == a2["ledger_head"]
    assert int(st["current"]) == a2["generation"]
    ents = ledger_entries()
    assert_chain(ents)
    assert ents[-1]["hash"] == a2["ledger_head"]
    manifest_recomputes(a2["generation"])

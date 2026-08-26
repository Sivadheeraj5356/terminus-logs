"""Verifier for abysslex WDM splice replan lab."""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

CTL = "/app/bin/splicectl"
REPORT = Path("/app/output/replan_report.json")
TRACE = Path("/app/output/lambda_trace.csv")
SETTLE = Path("/app/output/settle_score.tsv")
PUMP = Path("/app/var/splicekit/pump_ledger.json")
JOURNAL = Path("/app/var/splicekit/journal.jsonl")
SCEN = Path("/app/data/scenarios")
SNAPSHOT = Path("/opt/splicekit/scenarios-pristine")


def _env() -> dict[str, str]:
    e = os.environ.copy()
    prefix = "/usr/local/cargo/bin:/usr/local/go/bin:/app/bin"
    e["PATH"] = prefix + ":" + e.get("PATH", "")
    return e


def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        capture_output=True,
        text=True,
        cwd="/app",
        env=_env(),
    )


def _rebuild() -> None:
    _run(
        [
            "bash",
            "-lc",
            "cd /app/environment/oxk && cargo build --release --locked "
            "&& cp target/release/oxk-cli /app/bin/oxk-cli "
            "&& cd /app/environment && go build -o /app/bin/splicectl ./cmd/splicectl",
        ]
    )


def _restore() -> None:
    if SNAPSHOT.exists():
        if SCEN.exists():
            shutil.rmtree(SCEN)
        shutil.copytree(SNAPSHOT, SCEN)


def _sha256_hex(data: bytes) -> str:
    proc = subprocess.run(["sha256sum"], input=data, capture_output=True, check=True)
    return proc.stdout.decode().split()[0]


def knit(prev: int, at_regen: bool, free: list[int]) -> int | None:
    if not free:
        return None
    if prev < 0 or at_regen:
        return min(free)
    if prev in free:
        return prev
    return None


def draw(cool: float, channels: int, per_ch: float, cap: float) -> tuple[float, bool]:
    used = cool + channels * per_ch
    return used, used <= cap + 1e-9


def simulate(sid: str, cool0: dict[str, float] | None = None, prior_digest: str = "") -> dict:
    sc = json.loads((SCEN / f"{sid}.json").read_text())
    cool = dict(cool0 or {})
    cuts = set(sc.get("cuts") or [])
    regen = {n["id"]: bool(n["regen"]) for n in sc["nodes"]}
    spans = {s["id"]: s for s in sc["spans"]}
    adj: dict[str, list[tuple[str, str]]] = {}
    for s in sc["spans"]:
        if s["id"] in cuts:
            continue
        adj.setdefault(s["a"], []).append((s["id"], s["b"]))
        adj.setdefault(s["b"], []).append((s["id"], s["a"]))
    for k in adj:
        adj[k].sort(key=lambda x: x[0])

    demands = sorted(sc["demands"], key=lambda d: (d["priority"], d["id"]))
    used_lam: dict[str, set[int]] = {}
    used_ch: dict[str, int] = {}
    occ: dict[str, int] = {}
    hops: list[dict] = []
    served: list[str] = []
    rejected: list[str] = []
    peak = 0.0

    def path_key(ids: list[str]) -> str:
        return ">".join(ids)

    def shortest(src: str, dst: str) -> list[str] | None:
        from collections import deque

        q = deque([(src, [])])
        best = None
        cands: list[list[str]] = []
        dist = {src: 0}
        while q:
            node, path = q.popleft()
            if best is not None and len(path) > best:
                continue
            if node == dst and path:
                if best is None or len(path) < best:
                    best = len(path)
                    cands = [path[:]]
                elif len(path) == best:
                    cands.append(path[:])
                continue
            for sid2, nxt in adj.get(node, []):
                nd = len(path) + 1
                if best is not None and nd > best:
                    continue
                prevd = dist.get(nxt)
                if prevd is not None and prevd < nd:
                    continue
                dist[nxt] = nd
                q.append((nxt, path + [sid2]))
        if not cands:
            return None
        cands.sort(key=path_key)
        return cands[0]

    for d in demands:
        p = shortest(d["src"], d["dst"])
        if not p:
            rejected.append(d["id"])
            continue
        if any(occ.get(sid, 0) + d["gbps"] > spans[sid]["cap_gbps"] for sid in p):
            rejected.append(d["id"])
            continue
        at = d["src"]
        prev = -1
        tent: list[tuple[str, int]] = []
        ok = True
        for i, sid in enumerate(p):
            free = [x for x in spans[sid]["lambdas"] if x not in used_lam.get(sid, set())]
            free.sort()
            lam = knit(prev, regen[at], free)
            if lam is None:
                ok = False
                break
            tent.append((sid, lam))
            sp = spans[sid]
            at = sp["b"] if sp["a"] == at else sp["a"]
            prev = lam
        if not ok:
            rejected.append(d["id"])
            continue
        ch_add: dict[str, int] = {}
        for sid, _ in tent:
            ch_add[sid] = ch_add.get(sid, 0) + 1
        ok_p = True
        for sid, add in ch_add.items():
            used, ok2 = draw(
                float(cool.get(sid, 0.0)),
                used_ch.get(sid, 0) + add,
                float(sc["mw_per_channel"]),
                float(spans[sid]["pump_mw"]),
            )
            peak = max(peak, used)
            if not ok2:
                ok_p = False
                break
        if not ok_p:
            rejected.append(d["id"])
            continue
        for i, (sid, lam) in enumerate(tent):
            used_lam.setdefault(sid, set()).add(lam)
            used_ch[sid] = used_ch.get(sid, 0) + 1
            occ[sid] = occ.get(sid, 0) + d["gbps"]
            hops.append(
                {
                    "demand_id": d["id"],
                    "hop": i,
                    "span_id": sid,
                    "lambda": lam,
                    "gbps": d["gbps"],
                }
            )
        served.append(d["id"])

    for sid, ch in used_ch.items():
        used, _ = draw(
            float(cool.get(sid, 0.0)),
            ch,
            float(sc["mw_per_channel"]),
            float(spans[sid]["pump_mw"]),
        )
        cool[sid] = float(sc["cool_factor"]) * used
        peak = max(peak, used)

    # settle
    elig: dict[tuple[str, str], int] = {}
    serv: dict[tuple[str, str], int] = {}
    served_set = set(served)
    for d in sc["demands"]:
        a, b = d["peer_a"], d["peer_b"]
        if a > b:
            a, b = b, a
        elig[(a, b)] = elig.get((a, b), 0) + d["gbps"]
        if d["id"] in served_set:
            serv[(a, b)] = serv.get((a, b), 0) + d["gbps"]
    rows = []
    shares = []
    for a, b in sorted(elig.keys()):
        share = (serv.get((a, b), 0) / elig[(a, b)]) if elig[(a, b)] else 0.0
        rows.append((a, b, serv.get((a, b), 0), elig[(a, b)], f"{share:.4f}"))
        shares.append(share)
    score = sum(shares) / len(shares) if shares else 0.0

    by: dict[str, list[dict]] = {}
    for h in hops:
        by.setdefault(h["demand_id"], []).append(h)
    gbps = {d["id"]: d["gbps"] for d in sc["demands"]}
    lines = []
    for did in served:
        hs = sorted(by[did], key=lambda x: x["hop"])
        lines.append(
            "D|{}|path={}|lam={}|gbps={}".format(
                did,
                ">".join(h["span_id"] for h in hs),
                ",".join(str(h["lambda"]) for h in hs),
                gbps[did],
            )
        )
    body = "\n".join(sorted(lines)) + "\n"
    digest = _sha256_hex(body.encode())
    total = sum(gbps[i] for i in served)
    return {
        "scenario_id": sc["scenario_id"],
        "served": served,
        "rejected": rejected,
        "total_gbps": total,
        "pump_peak_mw": peak,
        "settle_score": score,
        "feasible": len(rejected) == 0,
        "prior_digest_hex": prior_digest,
        "digest_hex": digest,
        "hops": hops,
        "settle_rows": rows,
        "cool": cool,
        "digest_body": body,
    }


@pytest.fixture(scope="module", autouse=True)
def _module_setup():
    _restore()
    _rebuild()
    yield


def test_failed_run_unpublishable():
    """Unknown ids, empty demands, and publish-without-run exit non-zero without outputs."""
    _run([CTL, "reset"])
    for p in (REPORT, TRACE, SETTLE):
        if p.exists():
            p.unlink()
    r = _run([CTL, "run", "eq_missing_fixture"], check=False)
    assert r.returncode != 0
    assert not REPORT.exists()
    r2 = _run([CTL, "run", "eq_empty_demands"], check=False)
    assert r2.returncode != 0
    assert not REPORT.exists()
    r3 = _run([CTL, "publish"], check=False)
    assert r3.returncode != 0
    assert not REPORT.exists()


def test_admission_order_with_lane_audit():
    """Higher-priority demand is admitted when capacity binds after lane audit."""
    _run([CTL, "reset"])
    _run([CTL, "run", "eq_priority"])
    _run([CTL, "publish"])
    rep = json.loads(REPORT.read_text())
    exp = simulate("eq_priority")
    assert rep["served"] == exp["served"]
    assert "d_beta" in rep["served"]
    assert "d_alpha" in rep["rejected"]


def test_settle_share_values():
    """Settlement TSV shares match eligible/served replay."""
    _run([CTL, "reset"])
    _run([CTL, "run", "eq_priority"])
    _run([CTL, "publish"])
    exp = simulate("eq_priority")
    rows = list(csv.DictReader(SETTLE.open(), delimiter="\t"))
    assert len(rows) == len(exp["settle_rows"])
    for row, (a, b, sg, eg, sh) in zip(rows, exp["settle_rows"], strict=True):
        assert row["peer_a"] == a
        assert row["peer_b"] == b
        assert int(row["served_gbps"]) == sg
        assert int(row["eligible_gbps"]) == eg
        assert row["share"] == sh


def test_continuity_across_lane_staging():
    """Non-regenerator hops reuse prior channel after draft lane commits."""
    _run([CTL, "reset"])
    _run([CTL, "run", "eq_pacific"])
    _run([CTL, "publish"])
    exp = simulate("eq_pacific")
    rows = list(csv.DictReader(TRACE.open()))
    main = [r for r in rows if r["demand_id"] == "d_main"]
    assert main, "d_main should be routed"
    lams = [int(r["lambda"]) for r in sorted(main, key=lambda x: int(x["hop"]))]
    assert lams == [
        int(h["lambda"])
        for h in sorted(
            [x for x in exp["hops"] if x["demand_id"] == "d_main"],
            key=lambda x: x["hop"],
        )
    ]
    # continuity: equal lambdas across MD hops
    assert len(set(lams)) == 1


def test_regen_remux_after_lane_commit():
    """Regenerator hop may change channel when prior is occupied after lane commit."""
    _run([CTL, "reset"])
    _run([CTL, "run", "eq_regen_gap"])
    _run([CTL, "publish"])
    rep = json.loads(REPORT.read_text())
    exp = simulate("eq_regen_gap")
    assert "d_cross" in rep["served"]
    assert rep["served"] == exp["served"]
    rows = [r for r in csv.DictReader(TRACE.open()) if r["demand_id"] == "d_cross"]
    lams = [int(r["lambda"]) for r in sorted(rows, key=lambda x: int(x["hop"]))]
    assert lams[0] != lams[1]


def test_pump_audit_counts_staged_depth():
    """Pump audit rejects overflow when staged channel depth exceeds span cap."""
    _run([CTL, "reset"])
    _run([CTL, "run", "eq_pump_tight"])
    _run([CTL, "publish"])
    rep = json.loads(REPORT.read_text())
    exp = simulate("eq_pump_tight")
    assert rep["served"] == exp["served"]
    assert rep["rejected"] == exp["rejected"]
    assert len(rep["rejected"]) >= 1


def test_pump_cool_second_commit():
    """Cool residual from first commit constrains the second commit."""
    _run([CTL, "reset"])
    _run([CTL, "run", "eq_cool_stress"])
    cool1 = json.loads(PUMP.read_text())["cool"]
    assert cool1, "cool map should be non-empty after first commit"
    exp1 = simulate("eq_cool_stress")
    exp2 = simulate("eq_cool_stress", cool0=exp1["cool"], prior_digest=exp1["digest_hex"])
    _run([CTL, "run", "eq_cool_stress"])
    _run([CTL, "publish"])
    rep = json.loads(REPORT.read_text())
    assert rep["served"] == exp2["served"]
    assert rep["rejected"] == exp2["rejected"]
    assert len(rep["rejected"]) >= 1


def test_digest_matches_replay():
    """Report digest matches contract SHA-256 over sorted lines with newline."""
    _run([CTL, "reset"])
    _run([CTL, "run", "eq_pacific"])
    _run([CTL, "publish"])
    rep = json.loads(REPORT.read_text())
    exp = simulate("eq_pacific")
    assert rep["digest_hex"] == exp["digest_hex"]
    assert rep["digest_hex"] == _sha256_hex(exp["digest_body"].encode())


def test_status_digest_parity():
    """Status JSON digest and totals match published report."""
    _run([CTL, "reset"])
    _run([CTL, "run", "eq_pacific"])
    st = json.loads(_run([CTL, "status"]).stdout)
    _run([CTL, "publish"])
    rep = json.loads(REPORT.read_text())
    assert st["digest_hex"] == rep["digest_hex"]
    assert st["prior_digest_hex"] == rep["prior_digest_hex"]
    assert st["total_gbps"] == rep["total_gbps"]
    assert st["generation"] == rep["generation"]
    assert st["settle_score"] == pytest.approx(rep["settle_score"])


def test_generation_advances():
    """Journal generation advances across successful commits after reset."""
    _run([CTL, "reset"])
    _run([CTL, "run", "eq_priority"])
    _run([CTL, "publish"])
    g1 = json.loads(REPORT.read_text())["generation"]
    _run([CTL, "run", "eq_pump_tight"])
    _run([CTL, "publish"])
    g2 = json.loads(REPORT.read_text())["generation"]
    assert g1 == 1
    assert g2 == 2
    lines = JOURNAL.read_text().strip().splitlines()
    assert len(lines) == 2


def test_cross_artifact_consistency():
    """JSON, CSV, TSV, and pump ledger stay aligned for a published run."""
    _run([CTL, "reset"])
    _run([CTL, "run", "eq_pacific"])
    _run([CTL, "publish"])
    rep = json.loads(REPORT.read_text())
    exp = simulate("eq_pacific")
    assert set(rep["served"]) == set(exp["served"])
    assert rep["total_gbps"] == exp["total_gbps"]
    assert rep["feasible"] == exp["feasible"]
    assert rep["digest_hex"] == exp["digest_hex"]
    assert rep.get("prior_digest_hex", "") == exp["prior_digest_hex"]
    assert rep["settle_score"] == pytest.approx(exp["settle_score"])
    trace = list(csv.DictReader(TRACE.open()))
    assert {r["demand_id"] for r in trace} == set(exp["served"])
    cool = json.loads(PUMP.read_text())["cool"]
    for k, v in exp["cool"].items():
        assert cool[k] == pytest.approx(v)
    line = JOURNAL.read_text().strip().splitlines()[-1]
    parts = line.split("|")
    assert parts[0] == str(rep["generation"])
    assert parts[1] == rep["scenario_id"]
    assert parts[2] == rep["digest_hex"]


def test_shortest_path_via_lane_replay():
    """Equal-length shortest paths choose lexicographically smallest span sequence via lane replay."""
    _run([CTL, "reset"])
    _run([CTL, "run", "eq_path_tie"])
    _run([CTL, "publish"])
    exp = simulate("eq_path_tie")
    rows = list(csv.DictReader(TRACE.open()))
    path = ">".join(
        r["span_id"] for r in sorted(rows, key=lambda x: int(x["hop"]))
    )
    assert path == ">".join(h["span_id"] for h in sorted(exp["hops"], key=lambda x: x["hop"]))


def test_cool_factor_persistence():
    """Persisted cool residuals multiply committed draw by cool_factor."""
    _run([CTL, "reset"])
    _run([CTL, "run", "eq_cool_stress"])
    exp = simulate("eq_cool_stress")
    cool = json.loads(PUMP.read_text())["cool"]
    for k, v in exp["cool"].items():
        assert cool[k] == pytest.approx(v)


def test_journal_line_format():
    """Journal lines record generation, scenario id, and digest in order."""
    _run([CTL, "reset"])
    _run([CTL, "run", "eq_pacific"])
    _run([CTL, "publish"])
    rep = json.loads(REPORT.read_text())
    line = JOURNAL.read_text().strip().splitlines()[-1]
    parts = line.split("|")
    assert len(parts) == 3
    assert int(parts[0]) == rep["generation"]
    assert parts[1] == rep["scenario_id"]
    assert parts[2] == rep["digest_hex"]


def test_draft_lane_releases_on_reject():
    """Rejected admission attempts must not block later demands on shared spans."""
    _run([CTL, "reset"])
    _run([CTL, "run", "eq_regen_gap"])
    _run([CTL, "publish"])
    rep = json.loads(REPORT.read_text())
    exp = simulate("eq_regen_gap")
    assert rep["served"] == exp["served"]
    assert "d_cross" in rep["served"]


def test_held_out_priority_mutation():
    """Perturbed priority ordering is replayed from mutated fixture, not memorized."""
    src = SCEN / "eq_priority.json"
    backup = src.read_text()
    data = json.loads(backup)
    for d in data["demands"]:
        if d["id"] == "d_alpha":
            d["priority"] = 1
        elif d["id"] == "d_beta":
            d["priority"] = 5
    src.write_text(json.dumps(data, indent=2) + "\n")
    try:
        _run([CTL, "reset"])
        _run([CTL, "run", "eq_priority"])
        _run([CTL, "publish"])
        rep = json.loads(REPORT.read_text())
        exp = simulate("eq_priority")
        assert rep["served"] == exp["served"]
        assert "d_alpha" in rep["served"]
        assert "d_beta" in rep["rejected"]
    finally:
        src.write_text(backup)


def test_cool_idle_span_retention():
    """Cool residuals on idle spans survive a later commit on disjoint topology."""
    _run([CTL, "reset"])
    _run([CTL, "run", "eq_cool_stress"])
    cool_after = json.loads(PUMP.read_text())["cool"]
    assert cool_after, "first commit must leave cool residuals"
    retained = dict(cool_after)
    _run([CTL, "run", "eq_pacific"])
    cool_mid = json.loads(PUMP.read_text())["cool"]
    for sid, val in retained.items():
        assert sid in cool_mid
        assert cool_mid[sid] == pytest.approx(val)
    exp1 = simulate("eq_cool_stress")
    exp_pacific = simulate("eq_pacific", cool0=exp1["cool"], prior_digest=exp1["digest_hex"])
    exp2 = simulate(
        "eq_cool_stress",
        cool0=exp_pacific["cool"],
        prior_digest=exp_pacific["digest_hex"],
    )
    _run([CTL, "run", "eq_cool_stress"])
    _run([CTL, "publish"])
    rep = json.loads(REPORT.read_text())
    assert rep["served"] == exp2["served"]
    assert rep["rejected"] == exp2["rejected"]
    assert len(rep["rejected"]) >= 1


def test_held_out_gbps_mutation():
    """Settlement shares recompute under held-out demand size mutation."""
    src = SCEN / "eq_priority.json"
    backup = src.read_text()
    data = json.loads(backup)
    for d in data["demands"]:
        if d["id"] == "d_alpha":
            d["gbps"] = 12
        elif d["id"] == "d_beta":
            d["gbps"] = 8
    data["spans"][0]["cap_gbps"] = 15
    src.write_text(json.dumps(data, indent=2) + "\n")
    try:
        _run([CTL, "reset"])
        _run([CTL, "run", "eq_priority"])
        _run([CTL, "publish"])
        exp = simulate("eq_priority")
        rep = json.loads(REPORT.read_text())
        assert rep["served"] == exp["served"]
        assert rep["settle_score"] == pytest.approx(exp["settle_score"])
        rows = list(csv.DictReader(SETTLE.open(), delimiter="\t"))
        assert len(rows) == len(exp["settle_rows"])
        for row, (a, b, sg, eg, sh) in zip(rows, exp["settle_rows"], strict=True):
            assert row["peer_a"] == a
            assert row["peer_b"] == b
            assert int(row["served_gbps"]) == sg
            assert int(row["eligible_gbps"]) == eg
            assert row["share"] == sh
    finally:
        src.write_text(backup)


def test_mw_per_channel_mutation():
    """Pump admission recomputes under mutated mw_per_channel, not memorized."""
    src = SCEN / "eq_pump_tight.json"
    backup = src.read_text()
    data = json.loads(backup)
    data["mw_per_channel"] = 9.0
    src.write_text(json.dumps(data, indent=2) + "\n")
    try:
        _run([CTL, "reset"])
        _run([CTL, "run", "eq_pump_tight"])
        _run([CTL, "publish"])
        rep = json.loads(REPORT.read_text())
        exp = simulate("eq_pump_tight")
        assert rep["served"] == exp["served"]
        assert rep["rejected"] == exp["rejected"]
        assert len(rep["rejected"]) >= 1
    finally:
        src.write_text(backup)


def test_cap_bind_scenario():
    """Multi-hop capacity rejects when a shared span would overflow after an earlier admission."""
    _run([CTL, "reset"])
    _run([CTL, "run", "eq_cap_bind"])
    _run([CTL, "publish"])
    rep = json.loads(REPORT.read_text())
    exp = simulate("eq_cap_bind")
    assert rep["served"] == exp["served"]
    assert rep["rejected"] == exp["rejected"]
    assert "d_block" in rep["served"]
    assert "d_cross" in rep["rejected"]


def test_cap_audit_every_span_on_path():
    """Held-out cap_gbps mutation still binds on the tightest shared span after prior admissions."""
    src = SCEN / "eq_regen_gap.json"
    backup = src.read_text()
    data = json.loads(backup)
    for sp in data["spans"]:
        if sp["id"] == "s_ls_ld":
            sp["cap_gbps"] = 8
    src.write_text(json.dumps(data, indent=2) + "\n")
    try:
        _run([CTL, "reset"])
        _run([CTL, "run", "eq_regen_gap"])
        _run([CTL, "publish"])
        rep = json.loads(REPORT.read_text())
        exp = simulate("eq_regen_gap")
        assert rep["served"] == exp["served"]
        assert rep["rejected"] == exp["rejected"]
        assert "d_block" in rep["served"]
        assert "d_cross" in rep["rejected"]
    finally:
        src.write_text(backup)


def test_prior_digest_empty_on_first_commit():
    """First commit after reset carries an empty prior digest."""
    _run([CTL, "reset"])
    _run([CTL, "run", "eq_pacific"])
    _run([CTL, "publish"])
    rep = json.loads(REPORT.read_text())
    exp = simulate("eq_pacific", prior_digest="")
    assert rep["prior_digest_hex"] == ""
    assert rep["prior_digest_hex"] == exp["prior_digest_hex"]
    st = json.loads(_run([CTL, "status"]).stdout)
    assert st["prior_digest_hex"] == ""


def test_multi_run_journal_digest_chain():
    """Journal digests and prior_digest_hex chain across a multi-run session."""
    _run([CTL, "reset"])
    chain = ["eq_priority", "eq_pump_tight", "eq_path_tie"]
    digests: list[str] = []
    priors: list[str] = [""]
    cool: dict[str, float] = {}
    for sid in chain:
        exp = simulate(sid, cool0=cool, prior_digest=priors[-1])
        cool = exp["cool"]
        _run([CTL, "run", sid])
        _run([CTL, "publish"])
        rep = json.loads(REPORT.read_text())
        digests.append(rep["digest_hex"])
        assert rep["prior_digest_hex"] == exp["prior_digest_hex"]
        assert rep["digest_hex"] == exp["digest_hex"]
        assert rep["served"] == exp["served"]
        assert rep["generation"] == len(digests)
        priors.append(rep["digest_hex"])
    lines = JOURNAL.read_text().strip().splitlines()
    assert len(lines) == 3
    for i, line in enumerate(lines, start=1):
        parts = line.split("|")
        assert int(parts[0]) == i
        assert parts[2] == digests[i - 1]

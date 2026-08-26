"""Verifier for offline networkd bond ARP-monitor / ghost-peer reconcile.

Behavior-focused checks over the two-phase workflow, the durable lineage
ledger and settle chain, journal epochs, seal bindings, and the status probe.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
ENV = APP / "environment"
OUT_PATH = "/app/output/failover_report.json"
OUT = Path(OUT_PATH)
TRACE = APP / "output" / "run_traces" / "phase.jsonl"
JOURNAL = APP / "output" / "run_traces" / "session.journal"
STATE = APP / "output" / "runtime_state.json"
ARP_JRNL = APP / "output" / "arp_journal.jsonl"
SEAL = ENV / "meta" / "seal.bin"
STAGING = ENV / "meta" / "staging.json"
LINEAGE = ENV / "meta" / "lineage.json"
IDS = ENV / "docs" / "member_ids.txt"
BUMP = ENV / "data" / "bump_tbl.toml"
RANK = ENV / "data" / "rank_tbl.toml"
PERM = ENV / "data" / "perm_tbl.toml"

BUILT = ENV / "build" / "vx_bond"
PROBE = ENV / "build" / "bond_probe"
DRIVER = Path("/tmp/vx_run_verify")
PROBE_RUN = Path("/tmp/bond_probe_verify")

SEAL_BASE = '"axle": "0000000000000000"\n"rotor": "1111111111111111"\n'
LINEAGE_ZERO = {
    "pack_epoch": 0,
    "settle_epoch": 0,
    "seed": -1,
    "chain_prev": "",
    "chain_bind": "",
    "last_matrix": "",
}


def md5_16(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:16]


def expected_chain(prev: str, matrix: str, settle_epoch: int) -> str:
    """Settle-chain bind per formal rule 5b: the fold is the identity."""
    return md5_16(f"{prev}|{matrix}|{settle_epoch}")


def fixture_pressure(lane: str) -> int:
    h = 0
    for c in lane:
        h = (h * 131 + ord(c)) % (2**32)
    return 3 + (h % 3)


def rebuild() -> None:
    subprocess.run(
        [
            "bash",
            "-lc",
            "cd /app/environment && cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert BUILT.is_file(), "cmake build did not produce vx_bond driver"
    assert PROBE.is_file(), "cmake build did not produce bond_probe"
    DRIVER.write_bytes(BUILT.read_bytes())
    DRIVER.chmod(0o755)
    PROBE_RUN.write_bytes(PROBE.read_bytes())
    PROBE_RUN.chmod(0o755)
    Path("/app/bin").mkdir(parents=True, exist_ok=True)
    Path("/app/bin/vx_run").write_bytes(BUILT.read_bytes())
    Path("/app/bin/vx_run").chmod(0o755)


def write_zero_lineage() -> None:
    LINEAGE.write_text(json.dumps(LINEAGE_ZERO, indent=2) + "\n", encoding="utf-8")


def reset_outputs_keep_lineage() -> None:
    if (APP / "output" / "run_traces").exists():
        shutil.rmtree(APP / "output" / "run_traces")
    OUT.unlink(missing_ok=True)
    STATE.unlink(missing_ok=True)
    ARP_JRNL.unlink(missing_ok=True)
    (APP / "output").mkdir(parents=True, exist_ok=True)
    SEAL.write_text(SEAL_BASE, encoding="utf-8")


def reset_outputs() -> None:
    reset_outputs_keep_lineage()
    write_zero_lineage()


def run_vx(*extra: str) -> None:
    env = {**os.environ, "VX_ENV_ROOT": str(ENV)}
    env.pop("VX_REFRESHED", None)
    subprocess.run([str(DRIVER), *extra], check=True, capture_output=True, text=True, env=env)


def run_workflow(seed: int = 0) -> None:
    run_vx("--profile", "prep", "--variant-seed", str(seed), "--out", OUT_PATH)
    run_vx("--profile", "seal", "--variant-seed", str(seed), "--out", OUT_PATH)


def run_workflow_aliases(seed: int = 0) -> None:
    """Documented aliases: compile==prep, verify --hook replay==seal."""
    run_vx("--profile", "compile", "--variant-seed", str(seed), "--out", OUT_PATH)
    run_vx(
        "--profile",
        "verify",
        "--hook",
        "replay",
        "--variant-seed",
        str(seed),
        "--out",
        OUT_PATH,
    )


def run_bond_probe(report_path: Path = OUT) -> tuple[str, bool]:
    proc = subprocess.run(
        [str(PROBE_RUN), report_path.as_posix()],
        check=True,
        capture_output=True,
        text=True,
    )
    label = None
    converged = None
    for token in proc.stdout.strip().split():
        if token.startswith("label="):
            label = token.split("=", 1)[1]
        elif token.startswith("converged="):
            converged = token.split("=", 1)[1] == "1"
    assert label is not None and converged is not None, proc.stdout
    return label, converged


def load_report() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8"))


def load_lineage() -> dict:
    return json.loads(LINEAGE.read_text(encoding="utf-8"))


def load_ids() -> list[str]:
    return [ln.strip() for ln in IDS.read_text(encoding="utf-8").splitlines() if ln.strip()]


def go_format_float(x: float) -> str:
    s = format(x, ".16f").rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


def canonical_lane(lane_id: str) -> str:
    return lane_id[: -len("_echo")] if lane_id.endswith("_echo") else lane_id


def load_weights(seed: int = 0) -> dict[str, float]:
    weights: dict[str, float] = {}
    for line in BUMP.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        k, v = (x.strip() for x in line.split("=", 1))
        weights[k] = float(v)
    cur = -1
    shift = ""
    for line in PERM.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("seed"):
            cur = int(line.split("=", 1)[1].strip())
        if line.startswith("weight_shift") and cur == seed:
            shift = line.split("=", 1)[1].strip().strip('"')
    if shift:
        weights[shift] = weights.get(shift, 0.0) + 0.250
        echo = f"{shift}_echo"
        if echo in weights:
            weights[echo] = weights[echo] + 0.250
    return weights


def load_triple(seed: int) -> str:
    cur = -1
    triple = "x86_64-linux"
    for line in RANK.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("seed"):
            cur = int(line.split("=", 1)[1].strip())
        if line.startswith("triple") and cur == seed:
            triple = line.split("=", 1)[1].strip().strip('"')
    return triple


def expected_facet(member: str, triple: str, reloc: str, weight: float) -> str:
    return md5_16(f"{member}|{triple}|{reloc}|{go_format_float(weight)}")


def matrix_digest(rows: list[dict]) -> str:
    ordered = sorted(rows, key=lambda row: str(row["lane_id"]))
    parts = [
        f"{r['lane_id']}|{r['facet_hex']}|{int(r['loc_rc'])}|{int(r['img_rc'])}|{int(r['bind_rc'])}"
        for r in ordered
    ]
    return md5_16("|".join(parts))


def membership_digest(lanes: list[str]) -> str:
    return md5_16("bond|" + ",".join(lanes))


def journal_field(name: str) -> str | None:
    if not JOURNAL.exists():
        return None
    for line in JOURNAL.read_text(encoding="utf-8").splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip()
    return None


def journal_field_count(name: str) -> int:
    if not JOURNAL.exists():
        return 0
    return sum(
        1 for line in JOURNAL.read_text(encoding="utf-8").splitlines() if line.startswith(name + "=")
    )


def seal_key_count(lane: str) -> int:
    return SEAL.read_text(encoding="utf-8").count(f'"{lane}":')


def assert_facets_match_formula(report: dict, seed: int) -> None:
    weights = load_weights(seed)
    triple = load_triple(seed)
    for row in report["rows"]:
        lane = str(row["lane_id"])
        want = expected_facet(canonical_lane(lane), triple, "g2", weights[lane])
        assert row["facet_hex"] == want, (lane, row["facet_hex"], want)


def expected_compile_fp(seed: int) -> str:
    notes = ",".join(load_ids())
    return md5_16(f"{notes}|{load_triple(seed)}|{seed}")


def assert_journal_contract(seed: int) -> None:
    """Session journal and ARP lines must agree on compile_fp and membership_digest."""
    assert JOURNAL.is_file(), "session.journal missing"
    assert journal_field("compile_fp") == expected_compile_fp(seed)
    assert journal_field("membership_digest") == membership_digest(load_ids())
    assert journal_field("replay_ack") == "1"
    for field in ("epoch", "compile_fp", "membership_digest", "replay_ack"):
        assert journal_field_count(field) == 1, f"duplicate journal lines for {field}"
    digest = membership_digest(load_ids())
    assert ARP_JRNL.is_file(), "arp_journal.jsonl missing"
    for line in ARP_JRNL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        assert row["membership_digest"] == digest, row


def assert_chain_contract(report: dict) -> None:
    """Report summary must mirror a self-consistent lineage ledger."""
    lin = load_lineage()
    summ = report["summary"]
    assert lin["pack_epoch"] >= 1, lin
    assert lin["settle_epoch"] == lin["pack_epoch"], lin
    assert summ["pack_epoch"] == lin["pack_epoch"], (summ, lin)
    assert summ["settle_epoch"] == lin["settle_epoch"], (summ, lin)
    assert summ["chain_bind"] == lin["chain_bind"], (summ, lin)
    assert lin["last_matrix"] == summ["matrix_digest"], lin
    assert lin["chain_bind"] == expected_chain(
        lin["chain_prev"], lin["last_matrix"], lin["settle_epoch"]
    ), lin


def assert_coherent(report: dict, *, seed: int = 0) -> None:
    rows = report["rows"]
    assert report["summary"]["sync_label"] == "settled"
    assert report["summary"]["span_band"] == 0
    assert report["summary"]["rows_total"] == len(rows)
    by = {r["lane_id"]: r for r in rows}
    for r in rows:
        assert r["lag_code"] == 0
        assert r["loc_rc"] == r["img_rc"] == r["bind_rc"] == 1
        assert len(r["facet_hex"]) == 16
        assert all(c in "0123456789abcdef" for c in r["facet_hex"])
    for a, b in [("axle", "axle_echo"), ("rotor", "rotor_echo"), ("stator", "stator_echo")]:
        assert by[a]["facet_hex"] == by[b]["facet_hex"]
    assert journal_field("replay_ack") == "1"
    assert_journal_contract(seed)
    assert report["summary"]["matrix_digest"] == matrix_digest(rows)
    assert_facets_match_formula(report, seed)
    assert {r["lane_id"] for r in rows} == set(load_ids())
    assert_chain_contract(report)
    assert load_lineage()["seed"] == seed


def assert_not_coherent(report: dict, *, seed: int = 0) -> None:
    try:
        assert_coherent(report, seed=seed)
    except (AssertionError, KeyError, ValueError):
        return
    raise AssertionError("expected an incoherent report")


def reports_semantically_equal(a: dict, b: dict) -> bool:
    return (
        a["summary"]["sync_label"] == b["summary"]["sync_label"]
        and a["summary"]["span_band"] == b["summary"]["span_band"]
        and a["summary"]["matrix_digest"] == b["summary"]["matrix_digest"]
        and a["summary"]["rows_total"] == b["summary"]["rows_total"]
        and sorted(a["rows"], key=lambda r: r["lane_id"])
        == sorted(b["rows"], key=lambda r: r["lane_id"])
    )


@pytest.fixture(scope="session")
def built_driver():
    rebuild()
    return None


@pytest.fixture(autouse=True)
def _fresh(built_driver):
    reset_outputs()
    yield
    reset_outputs()


def test_nx_01(built_driver):
    """Full prep+seal settles with lineage-backed summary, traces, state, arp journal."""
    run_workflow(0)
    report = load_report()
    assert_coherent(report)
    assert TRACE.is_file() and TRACE.stat().st_size > 0
    assert JOURNAL.is_file()
    assert STATE.is_file()
    assert ARP_JRNL.is_file()
    state = json.loads(STATE.read_text(encoding="utf-8"))
    assert state["epoch"] >= 1
    assert len(state["lanes"]) == len(load_ids())
    lin = load_lineage()
    assert lin["pack_epoch"] == 1 and lin["settle_epoch"] == 1
    assert lin["chain_prev"] == ""
    assert lin["chain_bind"] == expected_chain("", report["summary"]["matrix_digest"], 1)


def test_nx_02(built_driver):
    """compile_fp and membership_digest match published material equations."""
    run_workflow(0)
    notes = ",".join(load_ids())
    assert journal_field("compile_fp") == md5_16(f"{notes}|{load_triple(0)}|0")
    assert journal_field("compile_fp") == expected_compile_fp(0)
    assert journal_field("membership_digest") == membership_digest(load_ids())
    assert_journal_contract(0)


def test_nx_03(built_driver):
    """Prep decays exactly once including the boundary lane (1 -> 0) and advances epoch."""
    ids = load_ids()
    digest = membership_digest(ids)
    STATE.write_text(
        json.dumps(
            {
                "epoch": 2,
                "lanes": [
                    {"lane_id": "axle", "pending_arp_pressure": 5, "membership_digest": digest},
                    {"lane_id": "rotor", "pending_arp_pressure": 1, "membership_digest": digest},
                    {"lane_id": "stator", "pending_arp_pressure": 0, "membership_digest": digest},
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    run_vx("--profile", "prep", "--variant-seed", "0", "--out", OUT_PATH)
    state = json.loads(STATE.read_text(encoding="utf-8"))
    assert state["epoch"] == 3
    by = {x["lane_id"]: x for x in state["lanes"]}
    assert by["axle"]["pending_arp_pressure"] == 4
    assert by["rotor"]["pending_arp_pressure"] == 0, "decay must reach zero at the boundary"
    assert by["stator"]["pending_arp_pressure"] == 0
    lines = [json.loads(ln) for ln in ARP_JRNL.read_text(encoding="utf-8").splitlines() if ln.strip()]
    rotor_line = next(x for x in lines if x["lane_id"] == "rotor")
    assert rotor_line["pending_after_decay"] == 0
    assert rotor_line["epoch"] == 3
    assert rotor_line["membership_digest"] == digest


def test_nx_04(built_driver):
    """Runtime epochs advance by exactly one per prep across consecutive preps."""
    run_vx("--profile", "prep", "--variant-seed", "0", "--out", OUT_PATH)
    first = json.loads(STATE.read_text(encoding="utf-8"))["epoch"]
    lin_first = load_lineage()["pack_epoch"]
    run_vx("--profile", "prep", "--variant-seed", "0", "--out", OUT_PATH)
    second = json.loads(STATE.read_text(encoding="utf-8"))["epoch"]
    lin_second = load_lineage()["pack_epoch"]
    run_vx("--profile", "prep", "--variant-seed", "0", "--out", OUT_PATH)
    third = json.loads(STATE.read_text(encoding="utf-8"))["epoch"]
    lin_third = load_lineage()["pack_epoch"]
    assert (first, second, third) == (1, 2, 3), "state epoch must advance by exactly one"
    assert (lin_first, lin_second, lin_third) == (1, 2, 3), "pack_epoch must advance by exactly one"


def test_nx_05(built_driver):
    """Seal isolates a lane whose journal digest mismatches even at matching epoch."""
    run_vx("--profile", "prep", "--variant-seed", "0", "--out", OUT_PATH)
    live_digest = membership_digest(load_ids())
    state = json.loads(STATE.read_text(encoding="utf-8"))
    lines = [json.loads(ln) for ln in ARP_JRNL.read_text(encoding="utf-8").splitlines() if ln.strip()]
    rotor_before = next(x for x in state["lanes"] if x["lane_id"] == "rotor")["pending_arp_pressure"]
    tampered = []
    for row in lines:
        item = dict(row)
        if item["lane_id"] == "axle":
            item["membership_digest"] = "f" * 16  # correct epoch, poisoned digest
            item["pending_after_decay"] = 77
        tampered.append(item)
    ARP_JRNL.write_text("\n".join(json.dumps(x) for x in tampered) + "\n", encoding="utf-8")
    run_vx("--profile", "seal", "--variant-seed", "0", "--out", OUT_PATH)
    after = json.loads(STATE.read_text(encoding="utf-8"))
    axle_after = next(x for x in after["lanes"] if x["lane_id"] == "axle")
    rotor_after = next(x for x in after["lanes"] if x["lane_id"] == "rotor")
    assert axle_after["pending_arp_pressure"] != 77, "digest-mismatched line must be isolated"
    assert rotor_after["pending_arp_pressure"] == rotor_before
    assert journal_field("membership_digest") == live_digest


def test_nx_06(built_driver):
    """Isolated lanes fall back to max(fixture, persisted), not the stale value."""
    ids = load_ids()
    digest = membership_digest(ids)
    run_vx("--profile", "prep", "--variant-seed", "0", "--out", OUT_PATH)
    state = json.loads(STATE.read_text(encoding="utf-8"))
    # Persisted pending 0 for axle, then poison its journal line: fallback must
    # be the fixture baseline, not 0 and not the poisoned value.
    for lane in state["lanes"]:
        if lane["lane_id"] == "axle":
            lane["pending_arp_pressure"] = 0
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    lines = [json.loads(ln) for ln in ARP_JRNL.read_text(encoding="utf-8").splitlines() if ln.strip()]
    tampered = []
    for row in lines:
        item = dict(row)
        if item["lane_id"] == "axle":
            item["epoch"] = item["epoch"] + 40
            item["pending_after_decay"] = 55
        tampered.append(item)
    ARP_JRNL.write_text("\n".join(json.dumps(x) for x in tampered) + "\n", encoding="utf-8")
    run_vx("--profile", "seal", "--variant-seed", "0", "--out", OUT_PATH)
    after = json.loads(STATE.read_text(encoding="utf-8"))
    axle_after = next(x for x in after["lanes"] if x["lane_id"] == "axle")
    assert axle_after["pending_arp_pressure"] == fixture_pressure("axle"), axle_after
    assert digest == membership_digest(load_ids())


def test_nx_07(built_driver):
    """Idempotent re-seal: report and lineage chain stay untouched."""
    run_workflow(0)
    first = load_report()
    assert_coherent(first)
    lin_first = load_lineage()
    run_vx("--profile", "seal", "--variant-seed", "0", "--out", OUT_PATH)
    second = load_report()
    assert reports_semantically_equal(first, second)
    lin_second = load_lineage()
    for key in ("pack_epoch", "settle_epoch", "chain_prev", "chain_bind", "last_matrix"):
        assert lin_first[key] == lin_second[key], key


def test_nx_08(built_driver):
    """Seal without prior prep cannot settle and leaves the zero lineage alone."""
    JOURNAL.unlink(missing_ok=True)
    ARP_JRNL.unlink(missing_ok=True)
    STATE.unlink(missing_ok=True)
    run_vx("--profile", "seal", "--variant-seed", "0", "--out", OUT_PATH)
    assert_not_coherent(load_report())
    lin = load_lineage()
    assert lin["settle_epoch"] == 0 and lin["chain_bind"] == ""


def test_nx_09(built_driver):
    """Stale compile_fp and membership_digest block seal until a prep refresh."""
    run_workflow(0)
    good_fp = journal_field("compile_fp")
    good_md = journal_field("membership_digest")
    assert good_fp == expected_compile_fp(0)
    assert good_md == membership_digest(load_ids())
    JOURNAL.write_text(
        "epoch=1\ncompile_fp=0000000000000000\nmembership_digest=ffffffffffffffff\nreplay_ack=1\n",
        encoding="utf-8",
    )
    run_vx("--profile", "seal", "--variant-seed", "0", "--out", OUT_PATH)
    assert_not_coherent(load_report())
    reset_outputs()
    run_workflow(0)
    assert_coherent(load_report(), seed=0)
    assert journal_field("compile_fp") == good_fp
    assert journal_field("membership_digest") == good_md


def test_nx_10(built_driver):
    """Repeated prep+seal leaves exactly one seal binding per lane and extends the chain."""
    run_workflow(0)
    lin_one = load_lineage()
    run_workflow(0)
    for lane in load_ids():
        assert seal_key_count(lane) == 1
    report = load_report()
    assert_coherent(report)
    lin_two = load_lineage()
    assert lin_two["pack_epoch"] == 2 and lin_two["settle_epoch"] == 2
    assert lin_two["chain_prev"] == lin_one["chain_bind"]
    assert lin_two["chain_bind"] == expected_chain(
        lin_one["chain_bind"], report["summary"]["matrix_digest"], 2
    )


def test_nx_11(built_driver):
    """Documented profile aliases compile/verify settle like prep/seal with chain parity."""
    run_workflow(0)
    bind_direct = load_lineage()["chain_bind"]
    reset_outputs()
    run_workflow_aliases(0)
    assert_coherent(load_report(), seed=0)
    assert load_lineage()["chain_bind"] == bind_direct


def test_nx_12(built_driver):
    """Driver and probe binaries (including /app/bin/vx_run) are present and executable."""
    for path in (BUILT, PROBE, DRIVER, PROBE_RUN, Path("/app/bin/vx_run")):
        assert path.is_file(), path
        mode = path.stat().st_mode
        assert mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH), path


def test_nx_13(built_driver):
    """Duplicate seal permits for one lane collapse to a single binding on seal refresh."""
    run_workflow(0)
    facet = {r["lane_id"]: r["facet_hex"] for r in load_report()["rows"]}["axle"]
    SEAL.write_text(
        f'"axle": "deadbeefdeadbeef"\n"axle": "cafebabecafebabe"\n"axle": "{facet}"\n'
        f'"rotor": "1111111111111111"\n',
        encoding="utf-8",
    )
    assert seal_key_count("axle") == 3
    run_vx("--profile", "seal", "--variant-seed", "0", "--out", OUT_PATH)
    assert seal_key_count("axle") == 1
    assert_coherent(load_report())


def test_nx_14(built_driver):
    """Migration recover restores from q2m, still settles, and continues the chain."""
    run_workflow(0)
    baseline = load_report()["summary"]["matrix_digest"]
    bind_before = load_lineage()["chain_bind"]
    SEAL.write_text('"axle": "deadbeefdeadbeef"\n', encoding="utf-8")
    subprocess.run(
        ["bash", "-lc", "VX_ENV_ROOT=/app/environment bash /app/environment/scripts/v2_recover.sh"],
        check=True,
        capture_output=True,
        text=True,
    )
    rebuild()
    reset_outputs_keep_lineage()
    run_workflow(0)
    report = load_report()
    assert_coherent(report)
    assert report["summary"]["matrix_digest"] == baseline
    lin = load_lineage()
    assert lin["chain_prev"] == bind_before, "recover must continue the chain, not restart it"
    assert lin["pack_epoch"] == 2 and lin["settle_epoch"] == 2
    assert lin["chain_bind"] == expected_chain(bind_before, baseline, 2)


def test_nx_15(built_driver):
    """Phase traces record prep then seal with member detail."""
    run_workflow(0)
    lines = [json.loads(ln) for ln in TRACE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    phases = [ln["phase"] for ln in lines]
    assert "prep" in phases and "seal" in phases
    assert any(load_ids()[0] in ln.get("detail", "") for ln in lines)


def test_nx_16(built_driver):
    """Every perm seed settles; weight-shift seeds change facet and matrix_digest."""
    run_workflow(0)
    base = load_report()
    assert_coherent(base, seed=0)
    base_rotor = {r["lane_id"]: r["facet_hex"] for r in base["rows"]}["rotor"]
    base_digest = base["summary"]["matrix_digest"]
    digests = {base_digest}
    for seed in range(4):
        reset_outputs()
        run_workflow(seed)
        report = load_report()
        assert_coherent(report, seed=seed)
        assert journal_field("compile_fp") == expected_compile_fp(seed)
        digests.add(report["summary"]["matrix_digest"])
    reset_outputs()
    run_workflow(2)
    shifted = load_report()
    assert_coherent(shifted, seed=2)
    shifted_rotor = {r["lane_id"]: r["facet_hex"] for r in shifted["rows"]}["rotor"]
    assert shifted_rotor != base_rotor
    assert shifted["summary"]["matrix_digest"] != base_digest
    assert len(digests) >= 2


def test_nx_17(built_driver):
    """Prep-only stays pending under the live probe; full seal settles."""
    run_vx("--profile", "prep", "--variant-seed", "0", "--out", OUT_PATH)
    label, converged = run_bond_probe(OUT)
    assert label == "pending" and not converged
    run_vx("--profile", "seal", "--variant-seed", "0", "--out", OUT_PATH)
    label2, converged2 = run_bond_probe(OUT)
    assert label2 == "settled" and converged2


def test_nx_18(built_driver):
    """Multiple ghosts and underscore heldouts never become rows."""
    original = STAGING.read_text(encoding="utf-8")
    try:
        STAGING.write_text(
            json.dumps(load_ids() + ["ghost0", "ghost1", "phantom", "_heldout_x", "_heldout_y"])
            + "\n",
            encoding="utf-8",
        )
        reset_outputs()
        run_workflow(0)
        report = load_report()
        lanes = [r["lane_id"] for r in report["rows"]]
        assert set(lanes) == set(load_ids())
        for stray in ("ghost0", "ghost1", "phantom", "_heldout_x", "_heldout_y"):
            assert stray not in lanes
        assert_coherent(report)
    finally:
        STAGING.write_text(original, encoding="utf-8")


def test_nx_19(built_driver):
    """Sequential settled workflows extend the chain link by link."""
    run_workflow(0)
    r1 = load_report()
    assert_coherent(r1)
    lin1 = load_lineage()
    reset_outputs_keep_lineage()
    run_workflow(0)
    r2 = load_report()
    assert_coherent(r2)
    lin2 = load_lineage()
    reset_outputs_keep_lineage()
    run_workflow(0)
    r3 = load_report()
    assert_coherent(r3)
    lin3 = load_lineage()
    d = r1["summary"]["matrix_digest"]
    assert reports_semantically_equal(r1, r2) and reports_semantically_equal(r2, r3)
    b1 = expected_chain("", d, 1)
    b2 = expected_chain(b1, d, 2)
    b3 = expected_chain(b2, d, 3)
    assert lin1["chain_bind"] == b1
    assert lin2["chain_bind"] == b2 and lin2["chain_prev"] == b1
    assert lin3["chain_bind"] == b3 and lin3["chain_prev"] == b2


def test_nx_20(built_driver):
    """Probe matches whitespace-agnostically: compact and spaced forms are one document."""
    compact = {
        "rows": [
            {
                "lane_id": "axle",
                "loc_rc": 1,
                "img_rc": 10,
                "bind_rc": 1,
                "lag_code": 0,
                "facet_hex": "0" * 16,
            }
        ],
        "summary": {
            "rows_total": 1,
            "sync_label": "settled",
            "span_band": 0,
            "matrix_digest": "0" * 16,
            "pack_epoch": 1,
            "settle_epoch": 1,
            "chain_bind": "0" * 16,
        },
    }
    syn = Path("/tmp/vx_probe_syn.json")
    syn.write_text(json.dumps(compact, separators=(",", ":")), encoding="utf-8")
    label, ok = run_bond_probe(syn)
    assert label == "pending" and not ok, "img_rc=10 must not satisfy the probe"

    compact["rows"][0]["img_rc"] = 1
    syn.write_text(json.dumps(compact, separators=(",", ":")), encoding="utf-8")
    label2, ok2 = run_bond_probe(syn)
    assert label2 == "settled" and ok2, "compact serialization must settle"

    syn.write_text(json.dumps(compact, indent=4), encoding="utf-8")
    label3, ok3 = run_bond_probe(syn)
    assert label3 == "settled" and ok3, "spaced serialization must settle identically"

    compact["summary"]["sync_label"] = "pending"
    syn.write_text(json.dumps(compact, separators=(",", ":")), encoding="utf-8")
    label4, ok4 = run_bond_probe(syn)
    assert label4 == "pending" and not ok4


def test_nx_21(built_driver):
    """Session journal epoch is stable across seal and fields appear exactly once."""
    run_vx("--profile", "prep", "--variant-seed", "1", "--out", OUT_PATH)
    epoch_prep = journal_field("epoch")
    assert epoch_prep is not None and int(epoch_prep) >= 1
    assert journal_field("compile_fp") == expected_compile_fp(1)
    run_vx("--profile", "seal", "--variant-seed", "1", "--out", OUT_PATH)
    assert journal_field("epoch") == epoch_prep
    assert journal_field("replay_ack") == "1"
    for field in ("epoch", "compile_fp", "membership_digest", "replay_ack"):
        assert journal_field_count(field) == 1, f"journal must not accumulate {field} lines"
    assert_coherent(load_report(), seed=1)


def test_nx_22(built_driver):
    """Alias verify without prior compile/prep cannot settle."""
    run_vx("--profile", "verify", "--hook", "replay", "--variant-seed", "0", "--out", OUT_PATH)
    assert_not_coherent(load_report())


def test_nx_23(built_driver):
    """Prep and seal with mismatched variant-seed must not settle as one workflow."""
    run_vx("--profile", "prep", "--variant-seed", "0", "--out", OUT_PATH)
    assert journal_field("compile_fp") == expected_compile_fp(0)
    run_vx("--profile", "seal", "--variant-seed", "1", "--out", OUT_PATH)
    report = load_report()
    assert_not_coherent(report, seed=1)
    assert journal_field("compile_fp") == expected_compile_fp(0)
    assert journal_field("compile_fp") != expected_compile_fp(1)
    assert load_lineage()["settle_epoch"] == 0


def test_nx_24(built_driver):
    """Poisoned lineage ledger refuses to settle until reset to zero lineage."""
    run_workflow(0)
    assert_coherent(load_report())
    lin = load_lineage()
    lin["chain_bind"] = "beadfeedbeadfeed"
    LINEAGE.write_text(json.dumps(lin, indent=2) + "\n", encoding="utf-8")
    reset_outputs_keep_lineage()
    run_workflow(0)
    assert_not_coherent(load_report())
    assert load_report()["summary"]["sync_label"] != "settled"
    write_zero_lineage()
    reset_outputs_keep_lineage()
    run_workflow(0)
    report = load_report()
    assert_coherent(report)
    lin2 = load_lineage()
    assert lin2["pack_epoch"] == 1 and lin2["chain_prev"] == ""


def test_nx_25(built_driver):
    """Lineage persists across output resets: chain history survives cleared /app/output."""
    run_workflow(0)
    bind_one = load_lineage()["chain_bind"]
    reset_outputs_keep_lineage()
    assert not OUT.exists() and not JOURNAL.exists()
    assert load_lineage()["chain_bind"] == bind_one
    run_workflow(0)
    report = load_report()
    assert_coherent(report)
    lin = load_lineage()
    assert lin["pack_epoch"] == 2
    assert lin["chain_prev"] == bind_one
    assert lin["chain_bind"] == expected_chain(bind_one, report["summary"]["matrix_digest"], 2)


def test_nx_26(built_driver):
    """Cross-seed settles form one chain whose links carry each seed's matrix."""
    run_workflow(0)
    r0 = load_report()
    assert_coherent(r0, seed=0)
    b1 = load_lineage()["chain_bind"]
    reset_outputs_keep_lineage()
    run_workflow(1)
    r1 = load_report()
    assert_coherent(r1, seed=1)
    lin = load_lineage()
    assert r1["summary"]["matrix_digest"] != r0["summary"]["matrix_digest"]
    assert lin["chain_prev"] == b1
    assert lin["chain_bind"] == expected_chain(b1, r1["summary"]["matrix_digest"], 2)
    assert lin["seed"] == 1

import json
import subprocess
from pathlib import Path

import pytest

OUT = Path("/app/output/out_h6.json")
RUN = "/app/tooling/run_h6.sh"
CMD_H6 = Path("/app/environment/tools/cmd_h6")
CKPT = Path("/app/var/h6_ckpt.json")
ENV = Path("/app/environment")
GRID = ENV / "fixtures" / "grid_v2.dat"
SNAP_V2 = ENV / "fixtures" / "snap_v2.dat"
EPOCH = ENV / "fixtures" / "lag_epoch_profiles.json"


def _run_env(extra: dict[str, str] | None = None, expect_fail: bool = False) -> None:
    import os

    env = os.environ.copy()
    if extra:
        env.update(extra)
    proc = subprocess.run(["bash", RUN], text=True, capture_output=True, check=False, env=env)
    if expect_fail:
        assert proc.returncode != 0, f"expected failure\nstdout={proc.stdout}\nstderr={proc.stderr}"
    else:
        assert proc.returncode == 0, f"command failed\nstdout={proc.stdout}\nstderr={proc.stderr}"


def _run(argv: list[str], expect_fail: bool = False) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(argv, text=True, capture_output=True, check=False)
    if expect_fail:
        assert proc.returncode != 0, f"expected failure: {argv}\n{proc.stdout}\n{proc.stderr}"
    else:
        assert proc.returncode == 0, f"command failed: {argv}\n{proc.stdout}\n{proc.stderr}"
    return proc


def _force_source_rebuild() -> None:
    if CMD_H6.exists():
        CMD_H6.unlink()


def _go_build() -> None:
    import os

    env = os.environ.copy()
    env["PATH"] = "/usr/local/go/bin:" + env.get("PATH", "")
    proc = subprocess.run(
        ["go", "build", "-o", "/app/environment/tools/cmd_h6", "./cmd_h6"],
        text=True,
        capture_output=True,
        check=False,
        cwd=str(ENV),
        env=env,
    )
    assert proc.returncode == 0, f"go build failed\nstdout={proc.stdout}\nstderr={proc.stderr}"


def _rebuild() -> None:
    _force_source_rebuild()
    _go_build()
    _clear_out()
    _run(["bash", RUN])


def _assert_meta_schema(doc: dict) -> None:
    meta = doc["meta"]
    assert set(meta.keys()) == {"run_tag", "cred_tag", "lane_a_win", "lane_b_win"}
    assert meta["run_tag"] == "h6"
    assert isinstance(meta["cred_tag"], str)
    assert isinstance(meta["lane_a_win"], int)
    assert isinstance(meta["lane_b_win"], int)


def _clear_out() -> None:
    if OUT.exists():
        OUT.unlink()


def _emit() -> dict:
    _clear_out()
    _run(["bash", RUN])
    doc = json.loads(OUT.read_text())
    _assert_meta_schema(doc)
    return doc


def _rows(doc: dict) -> list[dict]:
    return doc["rows"]


def _wit_fp(row: dict) -> str:
    raw = f"{row['lane_id']}|{row['nat_key']}|{row['sweep_gen']}|{row['ance_code']}|{row['bind_w']}"
    proc = subprocess.run(
        ["bash", "/app/environment/tooling/wit_check.sh", raw],
        text=True,
        capture_output=True,
        check=True,
    )
    return proc.stdout.strip()


def _roll_fp(rows: list[dict]) -> str:
    acc = 0
    ordered = sorted(rows, key=lambda r: (r["lane_id"], r["nat_key"]))
    for r in ordered:
        for b in r["wit_fp"].encode():
            acc = (acc * 131 + b) & 0xFFFFFFFFFFFF
        acc ^= (int(r["sweep_gen"]) << 16) & 0xFFFFFFFFFFFF
        acc ^= (int(r["phase_code"]) << 8) & 0xFFFFFFFFFFFF
    return f"{acc:016x}"


def _probe_scope(rows: list[dict]) -> int:
    """ASCII code of the first hex character of each row wit_fp, summed mod 1e6."""
    acc = 0
    for r in rows:
        wit = r.get("wit_fp", "")
        if wit:
            # Unambiguous: ord of first hex char, not int(wit[:2], 16).
            acc += ord(wit[0])
    return acc % 1_000_000


def _grid_wins() -> tuple[int, int, int]:
    text = GRID.read_text()
    lane_a = lane_b = cells = 0
    for tok in text.split():
        if tok.startswith("lane_a="):
            lane_a = int(tok.split("=", 1)[1])
        elif tok.startswith("lane_b="):
            lane_b = int(tok.split("=", 1)[1])
        elif tok.startswith("cells="):
            cells = int(tok.split("=", 1)[1])
    return lane_a, lane_b, cells


def _snap_spans() -> tuple[int, int]:
    lane_a = lane_b = 0
    for ln in SNAP_V2.read_text().splitlines():
        ln = ln.strip()
        if ln.startswith("lane_a_span="):
            lane_a = int(ln.split("=", 1)[1])
        elif ln.startswith("lane_b_span="):
            lane_b = int(ln.split("=", 1)[1])
    return lane_a, lane_b


def _epoch_lag_for(ticket: int) -> int:
    data = json.loads(EPOCH.read_text())
    pick = 0
    for row in data.get("epochs", []):
        if int(row["ticket"]) <= ticket and int(row["lag"]) > pick:
            pick = int(row["lag"])
    return pick


def _lane_rows(rows: list[dict], lane: str) -> list[dict]:
    return [r for r in rows if r["lane_id"] == lane]


def _find(rows: list[dict], lane: str, nat: int) -> dict | None:
    for r in rows:
        if r["lane_id"] == lane and int(r["nat_key"]) == nat:
            return r
    return None


def _span_hi(rows: list[dict], lane: str) -> int:
    xs = [int(r["nat_key"]) for r in rows if r["lane_id"] == lane]
    return max(xs) if xs else 0


@pytest.fixture(scope="session", autouse=True)
def _session_build() -> None:
    _rebuild()


def test_h0_grid_meta_bind() -> None:
    """meta lane wins come from grid_v2.dat and row bind_w matches meta without hop inflation."""
    doc = _emit()
    lane_a, lane_b, _ = _grid_wins()
    assert int(doc["meta"]["lane_a_win"]) == lane_a
    assert int(doc["meta"]["lane_b_win"]) == lane_b
    want = {"A": lane_a, "B": lane_b}
    for lane, width in want.items():
        for r in _lane_rows(_rows(doc), lane):
            assert int(r["bind_w"]) == width


def test_h1_snap_span_anchor() -> None:
    """After reset every row span_hi matches snap_v2 lane spans."""
    snap_a, snap_b = _snap_spans()
    _run_env({"H6_RESET": "1"})
    doc = json.loads(OUT.read_text())
    _assert_meta_schema(doc)
    rows = _rows(doc)
    assert rows
    for r in rows:
        if r["lane_id"] == "A":
            assert int(r["span_hi"]) == snap_a
        if r["lane_id"] == "B":
            assert int(r["span_hi"]) == snap_b


def test_h2_obs_align() -> None:
    """Each row wit_fp matches the disclosed digest and roll_fp matches the walk."""
    doc = _emit()
    for r in _rows(doc):
        assert r["wit_fp"] == _wit_fp(r)
    assert doc["roll_fp"] == _roll_fp(_rows(doc))


def test_h3_ckpt_codes() -> None:
    """Checkpoint sweep_gen, phase_code, span_hi, and wit_fp match live lane rows."""
    doc = _emit()
    for ck in doc["ckpts"]:
        live = _find(_rows(doc), ck["lane_id"], _span_hi(_rows(doc), ck["lane_id"]))
        assert live is not None
        assert int(ck["sweep_gen"]) == int(live["sweep_gen"])
        assert int(ck["phase_code"]) == int(live["phase_code"])
        assert int(ck["span_hi"]) == int(live["span_hi"])
        assert ck["wit_fp"] == live["wit_fp"]


def test_h4_epoch_lag_bind() -> None:
    """Warm cred b routes lane B marker_lag through lag_epoch_profiles and phase_code 3."""
    doc = _emit()
    assert doc["meta"]["cred_tag"] == "b"
    want_lag = _epoch_lag_for(5)
    assert want_lag > 0
    b_rows = _lane_rows(_rows(doc), "B")
    assert b_rows
    # Always assert: zeroed marker_lag must fail even when phase_code is forced.
    for r in b_rows:
        assert int(r["marker_lag"]) == want_lag
        assert int(r["phase_code"]) == 3


def test_h5_cross_h6() -> None:
    """Sweep and phase watermarks dominate row fields and roll_fp stays consistent."""
    doc = _emit()
    rows = _rows(doc)
    _, _, cells = _grid_wins()
    assert int(doc["sweep_wm"]) <= cells
    assert int(doc["sweep_wm"]) >= max(int(r["sweep_gen"]) for r in rows)
    assert int(doc["phase_wm"]) >= max(int(r["phase_code"]) for r in rows)
    assert doc["roll_fp"] == _roll_fp(rows)


def test_h6_stale_obs_recovery() -> None:
    """Reset plus dual chain recovers valid rows after a corrupted checkpoint wit_fp."""
    _emit()
    CKPT.write_text('[{"lane_id":"A","sweep_gen":1,"phase_code":1,"span_hi":99,"wit_fp":"0000000000000000"}]')
    _clear_out()
    _run_env({"H6_RESET": "1"})
    doc = json.loads(OUT.read_text())
    _assert_meta_schema(doc)
    assert _find(_rows(doc), "A", 10) is not None
    assert doc["roll_fp"] == _roll_fp(_rows(doc))


def test_h7_span_gate_s7() -> None:
    """Warm lane B emit aborts when prior lane A checkpoint span_hi drifts."""
    cold = _emit()
    for ck in cold["ckpts"]:
        if ck["lane_id"] == "A":
            ck["span_hi"] = int(ck["span_hi"]) + 5
    OUT.write_text(json.dumps(cold))
    _run_env({"H6_WARM_ONLY": "1"}, expect_fail=True)


def test_h8_quad_stable() -> None:
    """After settlement completes, four dual runs keep identical roll_fp, phase_wm, sweep_wm, and A:10 wit_fp."""
    _run_env({"H6_RESET": "1"})
    _run(["bash", RUN])  # second chain settles aborted voids
    fps: list[str] = []
    phases: list[int] = []
    sweeps: list[int] = []
    a10_wits: list[str] = []
    for _ in range(4):
        doc = _emit()
        fps.append(doc["roll_fp"])
        phases.append(int(doc["phase_wm"]))
        sweeps.append(int(doc["sweep_wm"]))
        row = _find(_rows(doc), "A", 10)
        assert row is not None
        a10_wits.append(row["wit_fp"])
    assert len(set(fps)) == 1
    assert len(set(phases)) == 1
    assert len(set(sweeps)) == 1
    assert len(set(a10_wits)) == 1


def test_h9_rerun_trap() -> None:
    """Deleting output then rerunning the driver rebuilds a non empty observation set."""
    _emit()
    OUT.write_text('{"meta":{"run_tag":"h6"},"rows":[],"ckpts":[]}')
    _run(["bash", RUN])
    doc = json.loads(OUT.read_text())
    assert len(_rows(doc)) >= 3
    assert doc["roll_fp"] == _roll_fp(_rows(doc))


def test_h10_delayed_echo() -> None:
    """First dual chain after reset keeps A:10 live; the next chain settles it to void."""
    _run_env({"H6_RESET": "1"})
    first = json.loads(OUT.read_text())
    _assert_meta_schema(first)
    r1 = _find(_rows(first), "A", 10)
    assert r1 is not None
    assert r1["row_kind"] == "live"
    _run(["bash", RUN])
    second = json.loads(OUT.read_text())
    _assert_meta_schema(second)
    r2 = _find(_rows(second), "A", 10)
    assert r2 is not None
    assert r2["row_kind"] == "void"
    assert int(r2["sweep_gen"]) >= 5


def test_h11_ceiling_b9() -> None:
    """After two dual chains, A:10 is void with sweep_gen at least five under grid ceiling."""
    _run_env({"H6_RESET": "1"})
    _run(["bash", RUN])
    doc = json.loads(OUT.read_text())
    _assert_meta_schema(doc)
    _, _, cells = _grid_wins()
    r = _find(_rows(doc), "A", 10)
    assert r is not None
    assert r["row_kind"] == "void"
    assert int(r["sweep_gen"]) >= 5
    assert int(doc["sweep_wm"]) <= cells


def test_h12_probe_wit_scope() -> None:
    """Every row probe_scope is the ASCII-first-hex-char sum mod 1e6, not evt_stamp max."""
    doc = _emit()
    rows = _rows(doc)
    want = _probe_scope(rows)
    assert rows
    for r in rows:
        assert int(r["probe_scope"]) == want
    evt_max = max(int(r["evt_stamp"]) for r in rows)
    if evt_max > want:
        assert want != evt_max

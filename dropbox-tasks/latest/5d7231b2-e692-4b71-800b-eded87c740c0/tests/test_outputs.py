"""Verifier for checkpoint-resume-optimizer-state."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
OUT = Path("/app/output")
WITNESS = OUT / "resume_witness.json"
TRACE_DIR = OUT / "traces"
DUR = ENV / "data/dur_k7.json"
SNAP = ENV / "data/snap_k7.json"
LIM = ENV / "data/lim_k7.toml"
HOLD = ENV / "data/hold_q3.toml"
CLI = "/app/environment/tools/drv_k7/drv_k7.js"
BUILD = "/app/environment/scripts/build_all.sh"
RST = "/app/environment/ops/rst7.sh"
MAIN = "/app/environment/t2/y5/src/main.js"
ID_LIST = ENV / "guide/id_list.txt"
POL = ENV / "guide/pol_table.md"
ABLATION = Path("/tests/ablation")

FRONTIER = [
    ENV / "n4/q7/src/VelP3.js",
    ENV / "n4/q7/src/ClkH8.js",
    ENV / "r8/w1/src/ArcM6.js",
    ENV / "r8/w1/src/MixZ4.js",
    ENV / "t2/y5/src/SealK9.js",
]

ABLATION_SCRIPTS = [
    ABLATION / "frontier_a.js",
    ABLATION / "frontier_b.js",
    ABLATION / "frontier_c.js",
    ABLATION / "frontier_d.js",
    ABLATION / "frontier_e.js",
]

PHASES = ["warm-probe", "train-base", "pause-store", "train-continue"]


def _fnv1a32(data: bytes) -> str:
    h = 0x811C9DC5
    for b in data:
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_lim() -> tuple[list[dict], list[dict]]:
    fixture_marker = "[[" + "fixture" + "]]"
    profile_marker = "[[" + "profile" + "]]"
    fixtures: list[dict] = []
    profiles: list[dict] = []
    section = None
    cur: dict | None = None
    for raw in LIM.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == fixture_marker:
            if cur and section == "fixture":
                fixtures.append(cur)
            cur = {}
            section = "fixture"
            continue
        if line == profile_marker:
            if cur and section == "fixture":
                fixtures.append(cur)
            elif cur and section == "profile":
                profiles.append(cur)
            cur = {}
            section = "profile"
            continue
        if "=" not in line or cur is None:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if val.startswith("["):
            cur[key] = [
                v.strip().strip('"') if '"' in v else float(v.strip())
                for v in val[1:-1].split(",")
                if v.strip()
            ]
            if key == "lv":
                cur[key] = [float(x) for x in cur[key]]
        else:
            val = val.strip('"')
            if key in {"ticks", "pause", "stride"}:
                cur[key] = int(val)
            elif key in {"band_max", "band_tail"}:
                cur[key] = float(val)
            else:
                cur[key] = val
    if cur:
        if section == "fixture":
            fixtures.append(cur)
        elif section == "profile":
            profiles.append(cur)
    return fixtures, profiles


def _parse_hold() -> list[dict]:
    hold_marker = "[[" + "hold" + "]]"
    hold: list[dict] = []
    cur: dict | None = None
    for raw in HOLD.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == hold_marker:
            if cur:
                hold.append(cur)
            cur = {}
            continue
        if "=" not in line or cur is None:
            continue
        key, _, val = line.partition("=")
        cur[key.strip()] = val.strip().strip('"')
    if cur:
        hold.append(cur)
    return hold


def _profile_map() -> dict[str, dict]:
    _fx, profiles = _parse_lim()
    return {p["name"]: p for p in profiles}


def _wipe_outputs() -> None:
    if OUT.exists():
        for p in sorted(OUT.rglob("*"), reverse=True):
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
    OUT.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)


def _reset_books() -> None:
    DUR.write_text('{"rows": {}}\n', encoding="utf-8")
    SNAP.write_text('{"probe_green": false, "rows": {}}\n', encoding="utf-8")


def _run_build() -> None:
    subprocess.run(["bash", BUILD], check=True, cwd="/app")


def _run_audit(*, expect_ok: bool = False) -> subprocess.CompletedProcess[str]:
    _wipe_outputs()
    _reset_books()
    _run_build()
    proc = subprocess.run(
        ["node", "/app/environment/tools/drv_k7/drv_k7.js", "--full-audit", "--out", "/app/output/resume_witness.json"],
        cwd="/app",
        capture_output=True,
        text=True,
    )
    if expect_ok:
        assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc


def _run_phases() -> None:
    for ph in PHASES:
        subprocess.run(["node", "/app/environment/t2/y5/src/main.js", ph], check=True, cwd="/app")


def _swap(idx: int) -> None:
    shutil.copy2(ABLATION_SCRIPTS[idx], FRONTIER[idx])


def _row_pairs(report: dict) -> list[tuple[dict, dict]]:
    grouped: dict[tuple[str, str], dict[str, dict]] = {}
    for row in report["rows"]:
        key = (row["fixture"], row["profile"])
        grouped.setdefault(key, {})[row["mode"]] = row
    out = []
    for key, modes in grouped.items():
        if "uninterrupted" in modes and "resume" in modes:
            out.append((modes["uninterrupted"], modes["resume"]))
    return out


@pytest.fixture(scope="session", autouse=True)
def baseline_audit() -> None:
    # Audit first (resets books), then driver phases for probe/.phase surfaces.
    _run_audit(expect_ok=True)
    _run_phases()


def test_q01_s1():
    """Terminal witness schema shape after full-audit."""
    report = _read_json(WITNESS)
    assert "summary" in report and "rows" in report
    assert "fixtures" in report["summary"]
    for row in report["rows"]:
        for key in ("fixture", "profile", "mode", "curve_digest", "band_drift", "band_tail"):
            assert key in row
        assert row["curve_digest"]
        assert row["mode"] in {"uninterrupted", "resume"}
        assert "_ok" not in row


def test_q02_c2():
    """Cross-resume curve_digest agreement for primary fixture/profile."""
    report = _read_json(WITNESS)
    u = next(r for r in report["rows"] if r["fixture"] == "ash" and r["profile"] == "strict_pair" and r["mode"] == "uninterrupted")
    r = next(r for r in report["rows"] if r["fixture"] == "ash" and r["profile"] == "strict_pair" and r["mode"] == "resume")
    assert u["curve_digest"] == r["curve_digest"]


def test_q03_p3():
    """Packing-sensitive fixture keeps resume and uninterrupted digests aligned."""
    report = _read_json(WITNESS)
    u = next(r for r in report["rows"] if r["fixture"] == "elm" and r["profile"] == "strict_pair" and r["mode"] == "uninterrupted")
    r = next(r for r in report["rows"] if r["fixture"] == "elm" and r["profile"] == "strict_pair" and r["mode"] == "resume")
    assert u["curve_digest"] == r["curve_digest"]


def test_q04_st4():
    """Continuity across pause/resume keeps curve_digest aligned."""
    report = _read_json(WITNESS)
    for u, r in _row_pairs(report):
        if u["fixture"] == "ash":
            assert u["curve_digest"] == r["curve_digest"]


def test_q05_b5():
    """Schedule-sensitive arm under rapid_k profile."""
    report = _read_json(WITNESS)
    prof = _profile_map()["rapid_k"]
    row = next(r for r in report["rows"] if r["fixture"] == "oak" and r["profile"] == "rapid_k" and r["mode"] == "uninterrupted")
    mate = next(r for r in report["rows"] if r["fixture"] == "oak" and r["profile"] == "rapid_k" and r["mode"] == "resume")
    assert row["curve_digest"] == mate["curve_digest"]
    assert row["band_drift"] <= prof["band_max"]


def test_q06_h6():
    """Numeric band class limits on long series."""
    report = _read_json(WITNESS)
    prof = _profile_map()["strict_pair"]
    for u, r in _row_pairs(report):
        assert u["band_drift"] <= prof["band_max"]
        assert u["band_tail"] <= prof["band_tail"]
        assert r["band_drift"] <= prof["band_max"]


def test_q07_x7():
    """Pairwise reduction matches published numeric order."""
    report = _read_json(WITNESS)
    fir_u = next(r for r in report["rows"] if r["fixture"] == "fir" and r["mode"] == "uninterrupted")
    fir_r = next(r for r in report["rows"] if r["fixture"] == "fir" and r["mode"] == "resume")
    assert fir_u["curve_digest"] == fir_r["curve_digest"]


def test_q08_s8():
    """Mid-probe false-green rejected as success."""
    snap = _read_json(SNAP)
    assert snap.get("probe_green")
    report = _read_json(WITNESS)
    dur = _read_json(DUR)
    for u, r in _row_pairs(report):
        kid = f"{u['fixture']}:{u['profile']}"
        assert u["curve_digest"] == r["curve_digest"]
        if kid in dur.get("rows", {}):
            trace = (TRACE_DIR / f"{u['fixture']}_{u['profile']}.bin").read_bytes()
            assert dur["rows"][kid]["hex"] == _fnv1a32(trace)


def test_q09_z9():
    """Long-schedule packing stress fixture."""
    report = _read_json(WITNESS)
    u = next(r for r in report["rows"] if r["fixture"] == "fir" and r["profile"] == "rapid_k" and r["mode"] == "uninterrupted")
    r = next(r for r in report["rows"] if r["fixture"] == "fir" and r["profile"] == "rapid_k" and r["mode"] == "resume")
    assert u["curve_digest"] == r["curve_digest"]


def test_q10_r10():
    """Cross-format curve_digest vs traces/*.bin."""
    report = _read_json(WITNESS)
    for row in report["rows"]:
        if row["mode"] != "uninterrupted":
            continue
        tag = f"{row['fixture']}_{row['profile']}"
        trace = (TRACE_DIR / f"{tag}.bin").read_bytes()
        body = trace[4:]
        assert row["curve_digest"] == _fnv1a32(body)


def test_q11_flip_v3():
    """Ablated packing module breaks elm strict_pair curve_digest agreement."""
    backup = FRONTIER[0].read_text(encoding="utf-8")
    try:
        _swap(0)
        _run_audit()
        report = _read_json(WITNESS)
        u = next(r for r in report["rows"] if r["fixture"] == "elm" and r["profile"] == "strict_pair" and r["mode"] == "uninterrupted")
        r = next(r for r in report["rows"] if r["fixture"] == "elm" and r["profile"] == "strict_pair" and r["mode"] == "resume")
        assert u["curve_digest"] != r["curve_digest"]
    finally:
        FRONTIER[0].write_text(backup, encoding="utf-8")
        _run_audit(expect_ok=True)


def test_q12_flip_h8():
    """Ablated clock module breaks ash strict_pair curve_digest agreement."""
    backup = FRONTIER[1].read_text(encoding="utf-8")
    try:
        _swap(1)
        _run_audit()
        report = _read_json(WITNESS)
        u = next(r for r in report["rows"] if r["fixture"] == "ash" and r["profile"] == "strict_pair" and r["mode"] == "uninterrupted")
        r = next(r for r in report["rows"] if r["fixture"] == "ash" and r["profile"] == "strict_pair" and r["mode"] == "resume")
        assert u["curve_digest"] != r["curve_digest"]
    finally:
        FRONTIER[1].write_text(backup, encoding="utf-8")
        _run_audit(expect_ok=True)


def test_q13_flip_m6():
    """Ablated schedule map breaks oak rapid_k curve_digest agreement."""
    backup = FRONTIER[2].read_text(encoding="utf-8")
    try:
        _swap(2)
        _run_audit()
        report = _read_json(WITNESS)
        u = next(r for r in report["rows"] if r["fixture"] == "oak" and r["profile"] == "rapid_k" and r["mode"] == "uninterrupted")
        r = next(r for r in report["rows"] if r["fixture"] == "oak" and r["profile"] == "rapid_k" and r["mode"] == "resume")
        assert u["curve_digest"] != r["curve_digest"]
    finally:
        FRONTIER[2].write_text(backup, encoding="utf-8")
        _run_audit(expect_ok=True)


def test_q14_flip_z4():
    """Ablated fold module breaks fir curve_digest agreement."""
    backup = FRONTIER[3].read_text(encoding="utf-8")
    try:
        _swap(3)
        _run_audit()
        report = _read_json(WITNESS)
        u = next(r for r in report["rows"] if r["fixture"] == "fir" and r["mode"] == "uninterrupted")
        r = next(r for r in report["rows"] if r["fixture"] == "fir" and r["mode"] == "resume")
        assert u["curve_digest"] != r["curve_digest"]
    finally:
        FRONTIER[3].write_text(backup, encoding="utf-8")
        _run_audit(expect_ok=True)


def test_q15_x15():
    """Held-out arm generalization."""
    report = _read_json(WITNESS)
    hold = _parse_hold()
    for h in hold:
        u = next(r for r in report["rows"] if r["fixture"] == h["fixture"] and r["profile"] == h["profile"] and r["mode"] == "uninterrupted")
        r = next(x for x in report["rows"] if x["fixture"] == h["fixture"] and x["profile"] == h["profile"] and x["mode"] == "resume")
        assert u["curve_digest"] == r["curve_digest"]


def test_q16_flip_k9():
    """Reverting durable finalize wiring desyncs book hex from trace body digest."""
    backup = FRONTIER[4].read_text(encoding="utf-8")
    try:
        _swap(4)
        _run_audit()
        report = _read_json(WITNESS)
        dur = _read_json(DUR)
        u = next(r for r in report["rows"] if r["fixture"] == "ash" and r["profile"] == "strict_pair" and r["mode"] == "uninterrupted")
        trace = (TRACE_DIR / f"{u['fixture']}_{u['profile']}.bin").read_bytes()
        kid = f"{u['fixture']}:{u['profile']}"
        assert dur["rows"][kid]["hex"] != _fnv1a32(trace[4:])
    finally:
        FRONTIER[4].write_text(backup, encoding="utf-8")
        _run_audit(expect_ok=True)


def test_q17_v17():
    """Multi-phase argv sequence / terminal convergence."""
    _run_audit(expect_ok=True)
    _run_phases()
    phase = _read_json(OUT / ".phase")
    assert phase.get("last") == "train-continue"
    report = _read_json(WITNESS)
    assert len(report["rows"]) >= 8


def test_q18_r18():
    """Idempotent rst7 recovery then re-audit."""
    first = _read_json(WITNESS)
    subprocess.run(["bash", "/app/environment/ops/rst7.sh"], check=True, cwd="/app")
    _run_audit(expect_ok=True)
    second = _read_json(WITNESS)
    assert first["summary"] == second["summary"]
    for a, b in zip(first["rows"], second["rows"]):
        assert a["curve_digest"] == b["curve_digest"]

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "/app/environment/tools")
from digest_hex import journal_tag, sha256_hex  # noqa: E402

ENV = Path("/app/environment")
WITNESS = Path("/app/output/witness.json")
STAGE = Path("/app/output/stage")
EPOCH = Path("/app/output/epoch.ledger")
SF = Path("/app/bin/sf_verify")
BUILD = Path("/app/build")
PROBE_SRC = Path(__file__).resolve().parent / "probes"
PROBE_BIN = Path("/tmp") / "sf_probes"


def _build():
    subprocess.run([str(ENV / "scripts" / "build_all.sh")], check=True)


def _lib(name: str) -> Path:
    return BUILD / ("lib" + name + ".a")


def _ensure_probes():
    """Compile verifier-owned probes against agent-built static libs (anti engine-hardcode)."""
    PROBE_BIN.mkdir(parents=True, exist_ok=True)
    specs = [
        ("seal", ["kz_core", "sf_bootstrap"], ENV / "core" / "kz"),
        ("compose", ["ep_lane", "sf_bootstrap"], ENV / "lane" / "ep"),
        ("quota", ["nx_lane", "sf_bootstrap"], ENV / "lane" / "nx"),
    ]
    bins = {}
    for kind, libs, include in specs:
        src = next(PROBE_SRC.glob("probe_" + kind + ".*"))
        out = PROBE_BIN / ("p_" + kind)
        link_libs = [str(_lib(lib)) for lib in libs]
        subprocess.run(
            ["g++", "-std=c++17", "-O0", str(src), "-o", str(out), "-I", str(include), *link_libs],
            check=True,
        )
        bins[{"seal": "seal-rotate", "compose": "compose-min", "quota": "quota-reload"}[kind]] = out
    return bins


def _run_matrix():
    subprocess.run(
        [
            str(SF),
            "--matrix",
            "all",
            "--profiles",
            "tight,loose",
            "--witness-out",
            str(WITNESS),
        ],
        check=True,
    )


def _load():
    assert WITNESS.exists(), "missing witness.json"
    return json.loads(WITNESS.read_text())


def _rows(data, bundle=None, profile=None):
    out = []
    for r in data["rows"]:
        if bundle and r["bundle"] != bundle:
            continue
        if profile and r["profile"] != profile:
            continue
        out.append(r)
    return out


def _probe(cmd):
    bins = _ensure_probes()
    return subprocess.run([str(bins[cmd])], capture_output=True, text=True, check=False)


@pytest.fixture(scope="module", autouse=True)
def _prepare():
    os.makedirs("/app/output/stage", exist_ok=True)
    os.makedirs("/app/output/logs", exist_ok=True)
    if EPOCH.exists():
        EPOCH.unlink()
    subprocess.run(["/app/environment/migrations/v2_hold.sh", "--recover"], check=False)
    _build()
    _ensure_probes()
    _run_matrix()
    _run_matrix()


def test_k01():
    """Module probe: seal rotation must close dual-valid at every generation step."""
    r = _probe("seal-rotate")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "dual_seq=0,0,0" in r.stdout
    assert "sealed=4" in r.stdout


def test_k02():
    """Module probe: idle soft refresh must not stretch absolute privilege window."""
    r = _probe("compose-min")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "abs=1100" in r.stdout
    assert "composed=1100" in r.stdout


def test_k03():
    """Module probe: fence reject, budget seat, reload-hold must not wipe occupancy."""
    r = _probe("quota-reload")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "occupancy=3" in r.stdout


def test_k04():
    """Skipped-gen circ_fence: dual peak stays closed across back-to-back seals."""
    data = _load()
    for r in _rows(data, bundle="circ_fence"):
        assert r["dual_valid"] == 0
        assert r["dual_peak"] == 0
        assert r["gen"] == 4
        assert r["synced_gen"] == 4
        assert r["status"] == "FRESH_OK"


def test_k05():
    """Rotation chain: three admits under advancing fences, stale fence ignored."""
    data = _load()
    for r in _rows(data, bundle="rot_chain"):
        assert r["dual_valid"] == 0
        assert r["dual_peak"] == 0
        assert r["gen"] == 3
        assert r["synced_gen"] == 3
        assert r["occupancy"] == 3
        assert r["occupancy"] <= r["limit"]
        assert r["status"] == "FRESH_OK"


def test_k06():
    """Long soft-refresh chain: composed equals frozen abs_deadline on both profiles."""
    data = _load()
    tight = _rows(data, bundle="clock_mix", profile="tight")[0]
    loose = _rows(data, bundle="clock_mix", profile="loose")[0]
    assert tight["abs_deadline"] == 1100
    assert tight["composed"] == 1100
    assert loose["abs_deadline"] == 1500
    assert loose["composed"] == 1500
    assert tight["composed"] != 1640
    assert loose["composed"] != 1800


def test_k07():
    """Burst admit path seats occupancy at the principal budget."""
    data = _load()
    for r in _rows(data, bundle="burst_cap"):
        assert r["occupancy"] <= r["limit"]
        assert r["occupancy"] == r["limit"]
        assert r["status"] == "FRESH_OK"


def test_k08():
    """Reclaim/admit fencing under login burst stays at limit across profiles."""
    data = _load()
    tight = _rows(data, bundle="burst_cap", profile="tight")[0]
    loose = _rows(data, bundle="burst_cap", profile="loose")[0]
    assert tight["occupancy"] == tight["limit"] == 3
    assert loose["occupancy"] == loose["limit"] == 5
    assert tight["status"] == "FRESH_OK"
    assert loose["status"] == "FRESH_OK"


def test_k09():
    """v2_hold recovery then matrix: reload-hold must not wipe burst seat."""
    samples = ENV / "samples" / "raw_bytes"
    hold = "/app/environment/migrations/v2_hold.sh"
    subprocess.run([hold], check=True)
    assert len(list(samples.glob("circ_a.bin"))) == 0
    subprocess.run([hold, "--recover"], check=True)
    assert len(list(samples.glob("circ_a.bin"))) == 1
    subprocess.run([hold], check=True)
    subprocess.run([hold, "--recover"], check=True)
    subprocess.run([hold, "--recover"], check=True)
    assert (samples / "circ_a.bin").read_bytes()[:4] == b"SF\x01\x00"
    marker = Path("/app/output/recovery.marker").read_text().strip()
    assert marker == "ok"
    _build()
    _run_matrix()
    data = _load()
    for r in _rows(data, bundle="burst_cap"):
        assert r["occupancy"] == r["limit"]
    assert data["meta"]["recovery_marker"] == "ok"


def test_k10():
    """Epoch ledger survives a second matrix; corruption then rebuild restores match."""
    assert EPOCH.exists()
    data = _load()
    assert data["meta"]["epoch_ok"] in ("ok", "seeded")
    _run_matrix()
    data2 = _load()
    assert data2["meta"]["epoch_ok"] == "ok"
    lines = [ln for ln in EPOCH.read_text().splitlines() if ln and not ln.startswith("#")]
    # two profiles × four bundles = eight ledger rows
    assert len(lines) >= 8
    assert len(lines) == 8
    EPOCH.write_text("# corrupted\nbad|line|0\n")
    _run_matrix()
    # Fresh write after corrupt prior yields seeded or drift then next pass ok
    _run_matrix()
    data4 = _load()
    assert data4["meta"]["epoch_ok"] == "ok"
    for r in _rows(data4, bundle="rot_chain"):
        assert r["dual_peak"] == 0
        assert r["occupancy"] == 3
    assert "rot_chain" in EPOCH.read_text()


def test_k11():
    """Stage omits integrity fields; journal counts match actual row key cardinality."""
    data = _load()
    stage_files = list(STAGE.glob("*.json"))
    assert stage_files
    stage_obj = json.loads(stage_files[0].read_text())
    assert "digest_sha256" not in stage_obj
    assert "journal_tag" not in stage_obj
    assert "dual_peak" in stage_obj
    assert "abs_deadline" in stage_obj
    row = data["rows"][0]
    assert "digest_sha256" in row and "journal_tag" in row
    assert data["meta"]["journal_field_count"] == len(row.keys())
    assert data["meta"]["stage_field_count"] == len(stage_obj.keys())
    assert data["meta"]["journal_field_count"] > data["meta"]["stage_field_count"]


def test_k12():
    """Cross-run idempotency of privilege windows and clock seating."""
    a = _load()
    _run_matrix()
    b = _load()
    keys = ("dual_peak", "composed", "abs_deadline", "occupancy", "gen")
    for ra, rb in zip(a["rows"], b["rows"]):
        assert ra["bundle"] == rb["bundle"] and ra["profile"] == rb["profile"]
        for k in keys:
            assert ra[k] == rb[k]


def test_k13():
    """Digest map and journal tags stay tied to raw_bytes across rot_chain material."""
    data = _load()
    for name, digest in data["digests"].items():
        raw = (ENV / "samples" / "raw_bytes" / name).read_bytes()
        assert sha256_hex(raw) == digest
    tags = set()
    for r in data["rows"]:
        expect = journal_tag(r["digest_sha256"], r["profile"], r["bundle"])
        assert r["journal_tag"] == expect
        tags.add(r["journal_tag"])
    assert len(tags) >= 4
    circ = _rows(data, bundle="circ_fence", profile="tight")[0]
    rot = _rows(data, bundle="rot_chain", profile="tight")[0]
    assert circ["digest_key"] != rot["digest_key"]
    assert circ["journal_tag"] != rot["journal_tag"]


def test_k14():
    """Interacting subsystems: rot_chain fence seat plus burst budget after recovery."""
    hold = "/app/environment/migrations/v2_hold.sh"
    subprocess.run([hold], check=True)
    subprocess.run([hold, "--recover"], check=True)
    if EPOCH.exists():
        EPOCH.unlink()
    _build()
    _run_matrix()
    _run_matrix()
    data = _load()
    assert data["meta"]["epoch_ok"] == "ok"
    assert data["meta"]["recovery_marker"] == "ok"
    for r in _rows(data, bundle="rot_chain"):
        assert r["dual_peak"] == 0
        assert r["occupancy"] == 3
        assert r["status"] == "FRESH_OK"
    for r in _rows(data, bundle="burst_cap"):
        assert r["occupancy"] == r["limit"]
    probe = _probe("seal-rotate")
    assert probe.returncode == 0
    probe = _probe("quota-reload")
    assert probe.returncode == 0

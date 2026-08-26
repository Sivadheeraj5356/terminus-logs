from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

APP = Path(os.environ.get("APP_DIR", "/app"))
DATA = APP / "data"
OUT = APP / "output"
PROGRAM = OUT / "program.json"
TRACES = OUT / "read_traces.json"
LOG = OUT / "measure_log.json"
REPORT = OUT / "integrity_report.json"

# Frozen outcomes for the shipped workload/manifest/policy fixtures.
# Tuple: (path, logged, check, verdict)
EXPECTED: dict[str, list[tuple[str, bool, str, str]]] = {
    "etc_hosts": [("/etc/hosts", True, "skip", "ok")],
    "var_syslog": [("/var/log/syslog", True, "skip", "ok")],
    "bin_tool": [("/usr/bin/tool", True, "pass", "ok")],
    "bin_evil": [("/usr/bin/evil", True, "fail", "bad")],
    "bin_ghost": [("/usr/bin/ghost", True, "pass", "ok")],
    "lib_ok": [("/lib/libc.so", True, "pass", "ok")],
    "lib_bad": [("/lib/bad.so", True, "fail", "bad")],
    "tmp_read": [("/tmp/scratch", False, "skip", "ok")],
    "usrlib_ok": [("/usr/lib/libhelper.so", True, "pass", "ok")],
    "usrlib_bad": [("/usr/lib/librogue.so", True, "fail", "bad")],
    "libre_office": [("/libreoffice/writer", False, "skip", "ok")],
    "usr_share": [("/usr/share/misc", True, "skip", "ok")],
    "bin_dupslash": [("/usr/bin//tool", True, "pass", "ok")],
    "sbin_daemon": [("/sbin/daemon", True, "pass", "ok")],
    "chain_hosts_bin": [
        ("/etc/hosts", True, "skip", "ok"),
        ("/usr/bin/tool", True, "pass", "ok"),
    ],
}


@pytest.fixture(scope="session", autouse=True)
def _built():
    proc = subprocess.run(
        ["bash", str(APP / "scripts" / "build.sh")],
        cwd=str(APP),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def _load(path: Path):
    assert path.exists(), f"{path} missing"
    return json.loads(path.read_text())


@pytest.fixture(scope="session")
def report():
    return _load(REPORT)


def _rows_by_path(log_doc):
    return {r["path"]: r for r in log_doc["rows"]}


def _job(report, name: str):
    return report["jobs"][[j["name"] for j in report["jobs"]].index(name)]


def test_outputs_present_and_schema(report):
    """Outputs exist with documented schema fields including set_id and events."""
    prog = _load(PROGRAM)
    assert isinstance(prog["clauses"], list) and prog["clauses"]
    assert report["schema"] == "integrity/v1"
    assert isinstance(report["set_id"], str) and report["set_id"]
    assert isinstance(report["aligned"], bool)
    traces = _load(TRACES)
    log_doc = _load(LOG)
    assert report["set_id"] == traces["set_id"] == log_doc["set_id"]
    for job in report["jobs"]:
        for ev in job["events"]:
            assert ev["check"] in {"pass", "fail", "skip"}
            assert ev["verdict"] in {"ok", "bad"}
            assert isinstance(ev["logged"], bool)


def test_measure_only_tier_still_logs(report):
    """Tier-zero measure-only reads still log and skip appraisal."""
    for name in ("etc_hosts", "var_syslog"):
        ev = _job(report, name)["events"][0]
        assert ev["logged"] is True, name
        assert ev["check"] == "skip", name
        assert ev["verdict"] == "ok", name


def test_shared_tier_logs_and_appraises(report):
    """Reads at a band carrying both logging and appraisal must do both successfully."""
    for name in ("bin_tool", "lib_ok"):
        ev = _job(report, name)["events"][0]
        assert ev["logged"] is True, name
        assert ev["check"] == "pass", name
        assert ev["verdict"] == "ok", name


def test_shared_tier_fail_still_logs(report):
    """Failed appraisal at a shared band must still produce the required digest row."""
    for name in ("bin_evil", "lib_bad"):
        ev = _job(report, name)["events"][0]
        assert ev["logged"] is True, name
        assert ev["check"] == "fail", name
        assert ev["verdict"] == "bad", name


def test_ghost_read_logged_and_passes(report):
    """A binary read must log and pass appraisal when the manifest matches."""
    ev = _job(report, "bin_ghost")["events"][0]
    assert ev["logged"] is True
    assert ev["check"] == "pass"
    assert ev["verdict"] == "ok"


def test_unscoped_read_skips(report):
    """Paths outside any attachment band skip logging and appraisal."""
    for name in ("tmp_read", "libre_office"):
        ev = _job(report, name)["events"][0]
        assert ev["logged"] is False, name
        assert ev["check"] == "skip", name
        assert ev["verdict"] == "ok", name


def test_broad_usr_measure_only(report):
    """A path covered only by the broad /usr measure attachment logs and skips appraisal."""
    ev = _job(report, "usr_share")["events"][0]
    assert ev["logged"] is True
    assert ev["check"] == "skip"
    assert ev["verdict"] == "ok"


def test_nested_bin_beats_broad_usr(report):
    """A nested /usr/bin path must use the tighter band, not the broad /usr band."""
    ev = _job(report, "bin_tool")["events"][0]
    assert ev["logged"] is True
    assert ev["check"] == "pass"
    assert ev["verdict"] == "ok"


def test_triple_appraisal_passes(report):
    """Reads at a band carrying log plus both appraisal kinds must satisfy all checks."""
    ev = _job(report, "usrlib_ok")["events"][0]
    assert ev["logged"] is True
    assert ev["check"] == "pass"
    assert ev["verdict"] == "ok"


def test_triple_appraisal_fail_still_logs(report):
    """Failed dual appraisal at a shared band must still produce the required digest row."""
    ev = _job(report, "usrlib_bad")["events"][0]
    assert ev["logged"] is True
    assert ev["check"] == "fail"
    assert ev["verdict"] == "bad"


def test_dupslash_logs_under_raw_path(report):
    """Duplicate slash reads log under the workload path with canonical manifest lookup."""
    ev = _job(report, "bin_dupslash")["events"][0]
    want_path = EXPECTED["bin_dupslash"][0][0]
    assert ev["path"] == want_path
    assert ev["logged"] is True
    assert ev["check"] == "pass"
    assert ev["verdict"] == "ok"
    rows = _rows_by_path(_load(LOG))
    assert want_path in rows
    manifest = _load(DATA / "manifest.json")
    assert rows[want_path]["digest_hex"] == manifest["/usr/bin/tool"]["digest_hex"]


def test_sbin_tier_logs_and_appraises(report):
    """Tier-three /sbin reads must log and pass HMAC appraisal."""
    ev = _job(report, "sbin_daemon")["events"][0]
    assert ev["logged"] is True
    assert ev["check"] == "pass"
    assert ev["verdict"] == "ok"


def test_chain_job_two_reads(report):
    """Multi-read jobs emit one event per read with independent enforcement."""
    evs = _job(report, "chain_hosts_bin")["events"]
    exp = EXPECTED["chain_hosts_bin"]
    assert len(evs) == len(exp)
    for rep, (path, logged, check, verdict) in zip(evs, exp):
        assert rep["path"] == path
        assert rep["logged"] == logged
        assert rep["check"] == check
        assert rep["verdict"] == verdict


def test_measure_log_matches_policy(report):
    """Digest rows cover exactly the paths the fixtures require logged."""
    log_doc = _load(LOG)
    rows = _rows_by_path(log_doc)
    manifest = _load(DATA / "manifest.json")
    for name, evs in EXPECTED.items():
        for path, want_log, _check, _verdict in evs:
            if want_log:
                assert path in rows, (name, path)
                canon = path.replace("//", "/")
                while "/./" in canon:
                    canon = canon.replace("/./", "/")
                assert rows[path]["digest_hex"] == manifest[canon]["digest_hex"]
            else:
                assert path not in rows, (name, path)


def test_no_spurious_measure_rows():
    """Digest rows must not include paths the winning band never required logged."""
    log_doc = _load(LOG)
    expected = set()
    for evs in EXPECTED.values():
        for path, want_log, _check, _verdict in evs:
            if want_log:
                expected.add(path)
    actual = {r["path"] for r in log_doc["rows"]}
    assert actual == expected, (actual - expected, expected - actual)


def test_report_aligned(report):
    """The run-level aligned flag must be true when every read satisfies the model."""
    assert report["aligned"] is True


def test_outcomes_match_reference(report):
    """Every per-read logged, check, and verdict field matches the fixture contract."""
    by_name = {j["name"]: j["events"] for j in report["jobs"]}
    for name, evs in EXPECTED.items():
        rep_evs = by_name[name]
        assert len(rep_evs) == len(evs), name
        for i, (path, logged, check, verdict) in enumerate(evs):
            rep = rep_evs[i]
            assert rep["path"] == path
            assert rep["logged"] == logged, (name, path, rep["logged"], logged)
            assert rep["check"] == check, (name, path, rep["check"], check)
            assert rep["verdict"] == verdict, (name, path, rep["verdict"], verdict)


def test_authority_pin_selects_production_bundle():
    """Lowered program must come from the production arm lane, not the staged overlay."""
    prog = _load(PROGRAM)
    roots = {c["root"] for c in prog["clauses"]}
    assert "/opt/bin" not in roots
    assert not any(c["tier"] >= 6 for c in prog["clauses"])
    assert "/usr/bin" in roots
    assert "/sbin" in roots


"""tests for the folding landscape inversion.

checks the reported estimator output against reference values for the shipped
study, and against a second study that only exists at verify time so the numbers
have to be computed rather than remembered.
"""
import glob
import json
import math
import os
import shutil
import sqlite3
import subprocess
from contextlib import contextmanager
from pathlib import Path

REPORT = Path("/app/output/report.json")
SRC = Path("/app/src")
BIN = Path("/app/bin/folding")
HELDOUT_SQL = Path("/tests/heldout_study.sql")
WORK = Path("/tmp/heldout_check")
HELDOUT_DB = WORK / "heldout_study.sqlite"
REBUILT = WORK / "folding_rebuilt"
RUN_CWD = "/tmp"
HELDOUT_TIMEOUT_S = 1200
BUILD_TIMEOUT_S = 300

FIELDS = ["c2", "cs", "log_d", "sigma_a", "sigma_b", "sigma_e",
          "se_c2", "se_cs", "se_log_d", "dev_cs", "f_half", "log_k_fold_zero"]

# Reference values, computed offline from an independent implementation of the
# model in MODEL.md, reading the same databases the container builds.
SHIP = {
    "c2": 6.005662076492248,
    "cs": 1.8279713054345608,
    "log_d": 6.233485407495714,
    "sigma_a": 0.17379886581655227,
    "sigma_b": 0.07779423687849955,
    "sigma_e": 0.13436033512373768,
    "se_c2": 0.08737989766204547,
    "se_cs": 0.19220534106343526,
    "se_log_d": 0.408575277468726,
    "dev_cs": 100.00245246685665,
    "f_half": 6.169342921338153,
    "log_k_fold_zero": -2.914793176919479,
}

HELD = {
    "c2": 5.2263316934406765,
    "cs": -1.1019281495174482,
    "log_d": 6.998530379780261,
    "sigma_a": 0.19888378549035998,
    "sigma_b": 0.09329266807162313,
    "sigma_e": 0.10766575123002453,
    "se_c2": 0.047586254334350236,
    "se_cs": 0.10732812073975895,
    "se_log_d": 0.2256471782269528,
    "dev_cs": 82.02273892043655,
    "f_half": 4.742343830917,
    "log_k_fold_zero": -0.6399425825882581,
}

RTOL_PARAM = 1e-3
RTOL_SE = 1e-2
RTOL_DEV = 1e-3
RTOL_DERIVED = 1e-4


def _load(path):
    with open(path) as fh:
        return json.load(fh)


def _close(report, key, want, rtol, where):
    got = report.get(key)
    assert isinstance(got, (int, float)) and not isinstance(got, bool), (
        f"{where}: {key} is missing or not a number: {got!r}")
    assert math.isfinite(got), f"{where}: {key} is not finite: {got!r}"
    tol = rtol * abs(want)
    assert abs(got - want) <= tol, (
        f"{where}: {key} is {got!r}, expected {want!r} "
        f"(tolerance {tol:.3e}, off by {abs(got - want):.3e})")


# ---------------------------------------------------------------- shipped study

_S = {}


def _study():
    """the report the analysis left for the shipped study; read once."""
    if not _S:
        _S["error"] = None
        _S["rep"] = None
        try:
            if not REPORT.is_file():
                raise AssertionError(f"{REPORT} was not produced")
            _S["rep"] = _load(REPORT)
            if not isinstance(_S["rep"], dict):
                raise AssertionError(f"{REPORT} is not a JSON object")
        except AssertionError as exc:
            _S["error"] = str(exc)
        except Exception as exc:
            _S["error"] = f"{REPORT} could not be read as JSON: {exc}"
    if _S["error"]:
        raise AssertionError(_S["error"])
    return _S["rep"]


# --------------------------------------------------------------- held-out study

@contextmanager
def _python_hidden():
    """take the interpreters off PATH for the duration of the held-out run."""
    moved = []
    for p in glob.glob("/usr/bin/python*") + glob.glob("/usr/local/bin/python*"):
        try:
            os.rename(p, p + ".hidden")
            moved.append(p)
        except OSError:
            pass
    try:
        yield
    finally:
        for p in moved:
            try:
                os.rename(p + ".hidden", p)
            except OSError:
                pass


_H = {}


def _heldout():
    """rebuild /app/src, run it on a study built here, and read the report.

    The outcome is cached before anything that can fail, so the subprocess is
    attempted exactly once however many tests ask for it.
    """
    if not _H:
        _H["error"] = None
        _H["rep"] = None
        try:
            _H["rep"] = _run_heldout()
        except AssertionError as exc:
            _H["error"] = str(exc)
        except Exception as exc:
            _H["error"] = f"held-out run failed: {exc}"
    if _H["error"]:
        raise AssertionError(_H["error"])
    return _H["rep"]


def _run_heldout():
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True, exist_ok=True)

    mlb = SRC / "folding.mlb"
    assert mlb.is_file(), f"{mlb} is missing, so the sources cannot be rebuilt"
    build = subprocess.run(["mlton", "-output", str(REBUILT), str(mlb)],
                           capture_output=True, text=True,
                           timeout=BUILD_TIMEOUT_S)
    assert build.returncode == 0, (
        "the sources under /app/src did not compile with mlton:\n"
        + (build.stderr or build.stdout)[-1500:])
    assert REBUILT.is_file(), "rebuilding /app/src produced no executable"

    con = sqlite3.connect(str(HELDOUT_DB))
    try:
        con.executescript(HELDOUT_SQL.read_text())
        con.commit()
    finally:
        con.close()

    out = WORK / "report.json"
    try:
        with _python_hidden():
            proc = subprocess.run([str(REBUILT), str(HELDOUT_DB), str(out)],
                                  capture_output=True, text=True, cwd=RUN_CWD,
                                  timeout=HELDOUT_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        raise AssertionError(
            f"the analysis did not finish the held-out study within "
            f"{HELDOUT_TIMEOUT_S}s")
    assert proc.returncode == 0, (
        "the analysis failed on the held-out study:\n"
        + (proc.stderr or proc.stdout)[-1500:])
    assert out.is_file(), "no report was written for the held-out study"
    return _load(out)


def _is_native(path):
    with open(path, "rb") as fh:
        magic = fh.read(4)
    return magic[:4] == b"\x7fELF" or magic[:4] in (
        b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe")


# ---------------------------------------------------------------------- tests

def test_report_is_written():
    """the analysis leaves a report at /app/output/report.json holding every
    reported quantity as a finite number."""
    rep = _study()
    missing = [k for k in FIELDS if k not in rep]
    assert not missing, f"{REPORT} is missing {missing}"
    bad = [k for k in FIELDS
           if not isinstance(rep[k], (int, float)) or isinstance(rep[k], bool)
           or not math.isfinite(rep[k])]
    assert not bad, f"{REPORT} has non-finite or non-numeric entries: {bad}"


def test_landscape_parameters():
    """the barrier scale, desolvation amplitude and diffusion coefficient
    recovered from the shipped study."""
    rep = _study()
    for k in ("c2", "cs", "log_d"):
        _close(rep, k, SHIP[k], RTOL_PARAM, "shipped study")


def test_noise_scales():
    """the three noise scales recovered from the shipped study."""
    rep = _study()
    for k in ("sigma_a", "sigma_b", "sigma_e"):
        _close(rep, k, SHIP[k], RTOL_PARAM, "shipped study")


def test_marginal_standard_errors():
    """marginal standard errors for the barrier scale, desolvation amplitude
    and diffusion coefficient."""
    rep = _study()
    for k in ("se_c2", "se_cs", "se_log_d"):
        _close(rep, k, SHIP[k], RTOL_SE, "shipped study")


def test_desolvation_deviance():
    """the deviance against a landscape carrying no desolvation feature."""
    _close(_study(), "dev_cs", SHIP["dev_cs"], RTOL_DEV, "shipped study")


def test_coexistence_force():
    """the force at which the unfolding and folding rates coincide."""
    _close(_study(), "f_half", SHIP["f_half"], RTOL_DERIVED, "shipped study")


def test_zero_load_folding_rate():
    """the folding rate extrapolated to zero load."""
    _close(_study(), "log_k_fold_zero", SHIP["log_k_fold_zero"], RTOL_DERIVED,
           "shipped study")


def test_native_executable_present():
    """the native executable is left at /app/bin/folding."""
    assert BIN.is_file(), f"{BIN} is missing"
    assert os.access(BIN, os.X_OK), f"{BIN} is not executable"
    assert _is_native(BIN), (
        f"{BIN} is not a native executable; a script in place of the compiled "
        "program does not satisfy this")


def test_sources_rebuild_as_standard_ml():
    """the analysis sources under /app/src are Standard ML and compile."""
    _heldout()
    assert REBUILT.is_file(), "rebuilding /app/src produced no executable"
    assert _is_native(REBUILT), "rebuilding /app/src produced no native binary"


def test_heldout_landscape_and_noise():
    """rebuilt from source and pointed at a study it has never seen, the
    analysis recovers that study's landscape and noise scales."""
    rep = _heldout()
    for k in ("c2", "cs", "log_d", "sigma_a", "sigma_b", "sigma_e"):
        _close(rep, k, HELD[k], RTOL_PARAM, "held-out study")


def test_heldout_uncertainty_and_derived():
    """on the held-out study the standard errors, the desolvation deviance and
    the two derived quantities are recomputed too."""
    rep = _heldout()
    for k in ("se_c2", "se_cs", "se_log_d"):
        _close(rep, k, HELD[k], RTOL_SE, "held-out study")
    _close(rep, "dev_cs", HELD["dev_cs"], RTOL_DEV, "held-out study")
    for k in ("f_half", "log_k_fold_zero"):
        _close(rep, k, HELD[k], RTOL_DERIVED, "held-out study")

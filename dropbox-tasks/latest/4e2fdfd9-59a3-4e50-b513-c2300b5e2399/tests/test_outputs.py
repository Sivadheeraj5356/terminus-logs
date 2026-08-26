"""Verifier for msgsigward-go-rfc9421-signature-base-audit (security audit).

The environment ships a COMPLETE RFC 9421 HTTP message-signature verifier
(`internal/msgsig/verify.go`) that contains several planted security defects:
each is a divergence from docs/security-spec.md that lets a forged, under-covered,
replayed, body-substituted, or algorithm-downgraded request through, or
mis-reports a rejection. The agent audits the immutable code against the spec and
writes /app/environment/findings.json — for each defect, a witness request bundle
on which the shipped verifier's decision is INSECURE.

Grading is purely behavioral and deterministic. An INDEPENDENT reference oracle
(oracle.py) gives the correct decision for any bundle; the shipped binary gives
the defective decision. A witness "exposes" a defect when the two decisions
diverge with that defect's signature. The task is solved iff the findings expose
every planted defect. The agent's source is never inspected; the shipped verifier
is never modified by the verifier; every reward comes from executed behavior.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

import oracle

ENV = Path("/app/environment")
BIN = "/tmp/msgsigward-bin"
CORPUS = Path(__file__).resolve().parent / "corpus"
FINDINGS = ENV / "findings.json"

GO_CRASH_SIGNATURES = (
    "panic:",
    "goroutine ",
    "runtime error",
    "fatal error",
    "signal sigsegv",
    "stack overflow",
    "out of memory",
)

REQUIRED_DEFECTS = {d[0] for d in oracle.AUDIT_DEFECTS}


@pytest.fixture(scope="session")
def binary():
    """Build the shipped (defective) msgsigward CLI once per session."""
    build = subprocess.run(
        ["go", "build", "-o", BIN, "./cmd/msgsigward"],
        cwd=str(ENV),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
    )
    assert build.returncode == 0, f"go build failed:\n{build.stdout}"
    return BIN


def _run(binary, input_bytes):
    f = Path(tempfile.mkstemp(suffix=".json")[1])
    try:
        f.write_bytes(input_bytes)
        return subprocess.run([binary, str(f)], capture_output=True, timeout=30)
    finally:
        f.unlink()


def _no_crash(r):
    low = r.stderr.decode(errors="replace").lower()
    for sig in GO_CRASH_SIGNATURES:
        assert sig not in low, f"crash signature {sig!r} present:\n{r.stderr!r}"


def shipped_decision(binary, case):
    """The shipped (defective) verifier's decision line, or 'UNEVALUATABLE'."""
    r = _run(binary, json.dumps(case).encode())
    _no_crash(r)
    if r.returncode != 0:
        return "UNEVALUATABLE"
    return r.stdout.decode().strip()


def oracle_decision(case):
    """The correct decision line from the independent oracle, or 'UNEVALUATABLE'."""
    try:
        return oracle.line(case)
    except oracle.ParseError:
        return "UNEVALUATABLE"


# --------------------------------------------------------------------------- #
# Task integrity: the shipped binary builds, runs, and diverges from the       #
# oracle ONLY in the planted-defect classes (a held-out battery of bundles).   #
# --------------------------------------------------------------------------- #
def test_binary_builds(binary):
    assert Path(binary).exists()


CORPUS_DIRS = (
    sorted(d.name for d in CORPUS.iterdir() if d.is_dir()) if CORPUS.exists() else []
)


def test_corpus_present():
    assert len(CORPUS_DIRS) >= 60, (
        f"expected the held-out battery, found {len(CORPUS_DIRS)}"
    )


@pytest.mark.parametrize("name", CORPUS_DIRS)
def test_shipped_diverges_only_in_planted_defects(binary, name):
    """Over the battery, the shipped verifier agrees with the independent oracle
    except in the planted-defect classes; the committed expectation equals the
    oracle (corpus integrity)."""
    vec = CORPUS / name
    case = json.loads((vec / "input.json").read_bytes())
    committed = (vec / "expected").read_text().strip()
    o = oracle_decision(case)
    assert committed == o, f"{name}: committed {committed!r} != oracle {o!r}"
    s = shipped_decision(binary, case)
    if s != o:
        assert oracle.classify_divergence(o, s) is not None, (
            f"{name}: shipped diverges from oracle in an UNPLANTED way: "
            f"oracle={o!r} shipped={s!r}"
        )


# --------------------------------------------------------------------------- #
# The deliverable: findings.json exposes every planted defect.                 #
# --------------------------------------------------------------------------- #
def _load_findings():
    assert FINDINGS.is_file(), "deliverable /app/environment/findings.json is missing"
    data = json.loads(FINDINGS.read_text())
    assert isinstance(data, dict) and isinstance(data.get("findings"), list), (
        'findings.json must be {"findings": [ {"witness": <bundle>, ...}, ... ]}'
    )
    return data["findings"]


def test_findings_present():
    findings = _load_findings()
    assert len(findings) >= len(REQUIRED_DEFECTS), (
        f"expected at least {len(REQUIRED_DEFECTS)} findings, got {len(findings)}"
    )
    for f in findings:
        assert isinstance(f, dict) and isinstance(f.get("witness"), dict), (
            "each finding needs a 'witness' request bundle (a JSON object)"
        )


def _exposed_defects(binary):
    findings = _load_findings()
    exposed = {}
    for f in findings:
        witness = f["witness"]
        s = shipped_decision(binary, witness)
        o = oracle_decision(witness)
        if s == o:
            continue  # not a divergence -> exposes nothing
        slug = oracle.classify_divergence(o, s)
        if slug is not None:
            exposed.setdefault(slug, (o, s))
    return exposed


def test_findings_witnesses_diverge(binary):
    """Every witness the agent supplies must expose a real, recognised defect
    (the shipped decision diverges from the oracle in a planted-defect class)."""
    findings = _load_findings()
    for i, f in enumerate(findings):
        witness = f["witness"]
        s = shipped_decision(binary, witness)
        o = oracle_decision(witness)
        assert s != o and oracle.classify_divergence(o, s) is not None, (
            f"finding[{i}]: witness does not expose a planted defect "
            f"(oracle={o!r} shipped={s!r})"
        )


@pytest.mark.parametrize("defect", sorted(REQUIRED_DEFECTS))
def test_defect_is_exposed(binary, defect):
    """Each planted defect must be exposed by at least one witness."""
    exposed = _exposed_defects(binary)
    assert defect in exposed, (
        f"no finding exposes the {defect!r} defect; exposed only {sorted(exposed)}"
    )

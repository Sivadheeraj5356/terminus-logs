"""Verifier for mailgate-rust-sender-authorization-spec.

Builds the agent's differential analyzer, runs it over a held-out corpus of Sender
Authorization Policy cases, and grades every certificate against an INDEPENDENT
dual reference (sap_ref.py) that models the intended Part 1 semantics, the
deployed engine's actual behaviour, and the partial models used to attribute
divergences.

The corpus under tests/corpus/ is never visible to the agent, and fresh per-run
cases with random names defeat hardcoding. The corpus is built so that no partial
model of the engine scores: it carries interaction queries (divergent, yet no
single deviation on its own accounts for the deployed result) and cancelling
queries (deviations are live but compose back to the intended result). The engine
is built from a verifier-owned pristine copy under tests/engine_src, and the
public tree is hash-checked unchanged, so nothing the agent writes under
environment/engine can affect the evidence the corpus is graded against.
"""

import hashlib
import json
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sap_ref as R  # noqa: E402

ENV = Path("/app/environment")
ANALYZER_SRC = ENV / "analyzer" / "src" / "main.rs"
PUBLIC_ENGINE_SRC = ENV / "engine" / "src"
PRISTINE_ENGINE_SRC = Path(__file__).resolve().parent / "engine_src"
ANALYZER_BIN = "/tmp/sap-analyzer"
ENGINE_BIN = "/tmp/sap-engine"
CORPUS = Path(__file__).resolve().parent / "corpus" / "cases.jsonl"

RUST_CRASH = (
    "panicked at",
    "stack overflow",
    "index out of bounds",
    "not implemented",
    "unimplemented",
)


def _load_corpus():
    out = []
    if CORPUS.exists():
        for line in CORPUS.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


CASES = _load_corpus()


# ---------------------------------------------------------------------------
# Build (zero-credit preconditions)
# ---------------------------------------------------------------------------
def _rustc(src, out):
    return subprocess.run(
        ["rustc", "--edition", "2021", "-O", str(src), "-o", out],
        cwd=str(ENV),
        capture_output=True,
        text=True,
        timeout=300,
    )


@pytest.fixture(scope="session")
def analyzer():
    r = _rustc(ANALYZER_SRC, ANALYZER_BIN)
    assert r.returncode == 0, f"analyzer build failed:\n{r.stdout}\n{r.stderr}"
    os.chmod(ANALYZER_BIN, 0o755)
    return ANALYZER_BIN


@pytest.fixture(scope="session")
def engine():
    r = _rustc(PRISTINE_ENGINE_SRC / "main.rs", ENGINE_BIN)
    assert r.returncode == 0, f"engine evidence does not build:\n{r.stdout}\n{r.stderr}"
    os.chmod(ENGINE_BIN, 0o755)
    return ENGINE_BIN


def test_engine_evidence_builds(engine):
    assert Path(engine).exists()


def test_public_engine_unchanged():
    """The read-only evidence must be exactly what the corpus was graded against."""
    pristine = sorted(PRISTINE_ENGINE_SRC.glob("*.rs"))
    assert pristine, "pristine engine source missing"
    for f in pristine:
        pub = PUBLIC_ENGINE_SRC / f.name
        assert pub.exists(), f"public engine file missing: {f.name}"
        want = hashlib.sha256(f.read_bytes()).hexdigest()
        got = hashlib.sha256(pub.read_bytes()).hexdigest()
        assert got == want, f"public engine file altered: {f.name}"


# ---------------------------------------------------------------------------
# Corpus shape and discrimination
# ---------------------------------------------------------------------------
def test_corpus_present():
    assert len(CASES) >= 40, f"too few cases: {len(CASES)}"
    total = sum(len(c["queries"]) for c in CASES)
    assert total >= 120, f"too few queries: {total}"
    for c in CASES:
        ids = [q["id"] for q in c["queries"]]
        assert len(ids) == len(set(ids)), f"{c['cid']}: duplicate query ids {ids}"
    div = 0
    classes = set()
    for c in CASES:
        for q in R.analyze_case(c)["queries"]:
            if q["divergent"]:
                div += 1
                classes.update(q["classes"])
    assert div >= 40, f"too few divergent queries: {div}"
    assert R.ALL_FAULTS <= classes, f"missing classes: {sorted(R.ALL_FAULTS - classes)}"


def test_every_fault_is_load_bearing():
    """No deviation may be omitted: dropping any one changes some corpus result.

    This is what stops a partial model of the engine from scoring. If a deviation
    could be left out and every result still matched, the corpus would not be
    testing it.
    """
    unexercised = []
    for f in sorted(R.ALL_FAULTS):
        without = R.ALL_FAULTS - {f}
        found = False
        for c in CASES:
            for q in c["queries"]:
                ip = R.parse_ip(q["ip"])
                if R.verdict(c["zone"], q["domain"], ip, without) != R.verdict(
                    c["zone"], q["domain"], ip, R.ALL_FAULTS
                ):
                    found = True
                    break
            if found:
                break
        if not found:
            unexercised.append(f)
    assert not unexercised, f"corpus never exercises these deviations: {unexercised}"


def test_corpus_defeats_isolated_fault_reasoning():
    """The corpus must punish reasoning about one deviation at a time.

    interaction: divergent, yet no single deviation on its own reproduces the
    deployed result — only the joint model does.
    cancelling: deviations are live but compose back to the intended result, so a
    per-deviation reading reports a divergence that is not there.
    """
    interaction = cancelling = 0
    for c in CASES:
        for q in R.analyze_case(c)["queries"]:
            interaction += bool(q["interaction"])
            cancelling += bool(q["cancelling"])
    assert interaction >= 8, f"too few interaction queries: {interaction}"
    assert cancelling >= 3, f"too few cancelling queries: {cancelling}"


def test_no_partial_model_scores():
    """Every proper subset of the deviations must get some corpus query wrong."""
    import itertools

    points = [
        (c["zone"], q["domain"], R.parse_ip(q["ip"]))
        for c in CASES
        for q in c["queries"]
    ]
    truth = [R.verdict(z, d, i, R.ALL_FAULTS) for (z, d, i) in points]
    faults = sorted(R.ALL_FAULTS)
    for r in range(len(faults)):
        for sub in itertools.combinations(faults, r):
            s = frozenset(sub)
            wrong = sum(
                1
                for k, (z, d, i) in enumerate(points)
                if R.verdict(z, d, i, s) != truth[k]
            )
            assert wrong > 0, f"partial model {sorted(s)} reproduces the whole corpus"


# ---------------------------------------------------------------------------
# Run helpers. Submitted code runs unprivileged and cannot read /tests.
# ---------------------------------------------------------------------------
def _drop_privs():
    p = pwd.getpwnam("sandbox")
    os.setgroups([])
    os.setgid(p.pw_gid)
    os.setuid(p.pw_uid)


def _write_case(case):
    """Hand the binary exactly the case-file shape Part 2 documents: zone, queries.

    A case's cid records which deviations it exercises; that is verifier
    bookkeeping, not input, and must not travel into the file being graded.
    """
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    payload = {"zone": case["zone"], "queries": case["queries"]}
    Path(path).write_text(json.dumps(payload), encoding="utf-8")
    os.chmod(path, 0o644)
    return path


def _run(binary, case, env=None, cwd=None, sandboxed=True):
    path = _write_case(case)
    try:
        return subprocess.run(
            [binary, path],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            cwd=cwd,
            preexec_fn=_drop_privs if sandboxed else None,
        )
    finally:
        os.unlink(path)


def _no_crash(r, label):
    err = (r.stderr or "").lower()
    for sig in RUST_CRASH:
        assert sig not in err, f"{label}: analyzer crashed ({sig!r}): {r.stderr}"
    assert r.returncode == 0, f"{label}: analyzer exit {r.returncode}: {r.stderr}"


def _certs(r, label, n):
    try:
        obj = json.loads(r.stdout)
    except Exception as e:  # noqa: BLE001
        pytest.fail(f"{label}: analyzer stdout is not JSON ({e}): {r.stdout[:300]!r}")
    assert isinstance(obj, dict) and "queries" in obj, f"{label}: no 'queries' key"
    got = obj["queries"]
    assert len(got) == n, f"{label}: expected {n} certificates, got {len(got)}"
    return got


def _engine_results(engine, case):
    r = _run(engine, case, sandboxed=False)
    err = (r.stderr or "").lower()
    for sig in RUST_CRASH:
        assert sig not in err, f"engine crashed ({sig!r}): {r.stderr}"
    assert r.returncode == 0, f"engine exit {r.returncode}: {r.stderr}"
    out = {}
    for line in r.stdout.splitlines():
        if "\t" in line:
            k, v = line.split("\t", 1)
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# The frozen engine binary must equal the DEPLOYED reference exactly. This
# anchors the evidence: the agent reverse-engineers the same behaviour.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("idx", range(len(CASES)))
def test_engine_matches_deployed_reference(engine, idx):
    case = CASES[idx]
    got = _engine_results(engine, case)
    for q in case["queries"]:
        want = R.verdict(case["zone"], q["domain"], R.parse_ip(q["ip"]), R.ALL_FAULTS)
        assert got.get(q["id"]) == want, (
            f"{case['cid']}/{q['id']}: engine {got.get(q['id'])!r} != deployed reference {want!r}"
        )


# ---------------------------------------------------------------------------
# Grade the agent's certificates.
# ---------------------------------------------------------------------------
def _grade(certs, case, label):
    want = R.analyze_case(case)["queries"]
    by_id = {c.get("id"): c for c in certs}
    for w in want:
        c = by_id.get(w["id"])
        assert c is not None, f"{label}: no certificate for query {w['id']}"
        assert c.get("deployed") == w["deployed"], (
            f"{label}/{w['id']}: deployed {c.get('deployed')!r} != {w['deployed']!r}"
        )
        assert c.get("intended") == w["intended"], (
            f"{label}/{w['id']}: intended {c.get('intended')!r} != {w['intended']!r}"
        )
        assert c.get("divergent") == w["divergent"], (
            f"{label}/{w['id']}: divergent {c.get('divergent')!r} != {w['divergent']!r}"
        )
        if w["divergent"]:
            assert c.get("witness") == w["witness"], (
                f"{label}/{w['id']}: witness {c.get('witness')!r} != {w['witness']!r}"
            )
        else:
            assert c.get("witness") is None, (
                f"{label}/{w['id']}: witness must be null on a non-divergent query, "
                f"got {c.get('witness')!r}"
            )


@pytest.mark.parametrize("idx", range(len(CASES)))
def test_corpus_case(analyzer, idx):
    case = CASES[idx]
    r = _run(analyzer, case)
    _no_crash(r, case["cid"])
    certs = _certs(r, case["cid"], len(case["queries"]))
    _grade(certs, case, case["cid"])


# ---------------------------------------------------------------------------
# Fresh per-run cases: random names, composite shapes. Defeats hardcoding.
# ---------------------------------------------------------------------------
def _fresh_cases():
    """Per-run cases, returned as (kind, case). The run tag randomises the zone.

    kind is the pytest id and is stable across runs; only the case's own cid
    carries the tag, so a failure still names the exact instance. Putting the tag
    in the id would give every run its own one-off test name, and one failing run
    would then read as a test that no run ever passed.
    """
    out = []
    tag = uuid.uuid4().hex[:8]

    def add(kind, zone, queries):
        out.append((kind, {"cid": f"{kind}-{tag}", "zone": zone, "queries": queries}))

    v, rel = f"v{tag}.example", f"r{tag}.example"
    burn = " ".join(["a"] * 7)
    add(
        "fresh-interaction",
        {
            v: {"sap": f"v=sap1 {burn} redirect={rel}", "a": ["198.51.100.10"]},
            rel: {"sap": "v=sap1 a", "a": ["203.0.113.99"]},
        },
        [{"id": "a", "domain": v, "ip": "203.0.113.99"}],
    )
    d = f"c{tag}.example"
    add(
        "fresh-cancelling",
        {d: {"sap": "v=sap1 ?ip4:203.0.113.64/26 +ip4:203.0.113.0/25", "a": []}},
        [{"id": "a", "domain": d, "ip": "203.0.113.10"}],
    )
    e = f"i{tag}.example"
    add(
        "fresh-cidr-last",
        {e: {"sap": "v=sap1 +ip4:198.51.100.0/25 ?ip4:198.51.100.64/26", "a": []}},
        [{"id": "a", "domain": e, "ip": "198.51.100.5"}],
    )
    return out


FRESH = _fresh_cases()


@pytest.mark.parametrize("case", [c for _, c in FRESH], ids=[k for k, _ in FRESH])
def test_generated_case(analyzer, engine, case):
    # the engine agrees with the deployed reference on the fresh case too
    got = _engine_results(engine, case)
    for q in case["queries"]:
        want = R.verdict(case["zone"], q["domain"], R.parse_ip(q["ip"]), R.ALL_FAULTS)
        assert got.get(q["id"]) == want, f"{case['cid']}: engine != deployed reference"
    r = _run(analyzer, case)
    _no_crash(r, case["cid"])
    certs = _certs(r, case["cid"], len(case["queries"]))
    _grade(certs, case, case["cid"])


def test_generated_cases_cover_composites():
    kinds = {"interaction": 0, "cancelling": 0}
    for _, c in FRESH:
        for q in R.analyze_case(c)["queries"]:
            if q["interaction"]:
                kinds["interaction"] += 1
            if q["cancelling"]:
                kinds["cancelling"] += 1
    assert kinds["interaction"] >= 1, (
        f"fresh cases lost their interaction query: {kinds}"
    )
    assert kinds["cancelling"] >= 1, f"fresh cases lost their cancelling query: {kinds}"


# ---------------------------------------------------------------------------
# The analyzer must carry its own model of the engine.
# ---------------------------------------------------------------------------
def test_analyzer_does_not_lean_on_the_engine(analyzer):
    """Shelling out to the engine may not substitute for modelling it.

    The engine sources are moved out of reach, no prebuilt engine binary is
    available, and PATH is emptied. A correct analyzer is unaffected.
    """
    case = CASES[0]
    stash = Path("/tmp") / f"engine-stash-{uuid.uuid4().hex}"
    for b in (ENGINE_BIN, "/tmp/oracle-analyzer"):
        if Path(b).exists():
            os.unlink(b)
    shutil.move(str(ENV / "engine"), str(stash))
    try:
        env = dict(os.environ)
        env["PATH"] = "/nonexistent"
        r = _run(analyzer, case, env=env, cwd="/tmp")
        _no_crash(r, "engine-out-of-reach")
        certs = _certs(r, "engine-out-of-reach", len(case["queries"]))
        _grade(certs, case, "engine-out-of-reach")
    finally:
        shutil.move(str(stash), str(ENV / "engine"))

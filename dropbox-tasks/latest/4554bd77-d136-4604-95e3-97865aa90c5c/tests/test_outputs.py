"""Behavioral verifier for the render-pipeline plugin resolver.

Rebuilds the program from the C++ source in /app and runs the compiled binary
over a hidden corpus of resolution cases plus the published example fixtures,
checking each case's install set and conflict records against the reference
ground truth. Every case is scored independently so a partial implementation is
caught on the specific behaviours it gets wrong.

The answer files are locked to root-only and BOTH the compile and every graded
run happen as the unprivileged ``nobody`` user. Because the candidate controls
the source, compiling as root would let a build step (a wrapper script, a code
generator, or a preprocessor ``#include`` / ``#embed`` of the answer file) read
the locked answer key and bake the expected results into the binary; compiling as
``nobody`` with the answer files unreadable closes that hole.
"""
import grp
import json
import os
import pathlib
import pwd
import shutil
import subprocess

import pytest

APP = "/app"
SOURCE = "/app/main.cpp"
BUILD_DIR = "/tmp/rpresolve-build"       # nobody-owned build output dir
BINARY = BUILD_DIR + "/rpresolve"
NOBODY_HOME = "/tmp/nobody-home"         # nobody-writable HOME / TMPDIR
ANSWER_FILES = ("/tests/vectors.json", "/tests/examples.json")

TESTS = pathlib.Path("/tests")
VECTORS = json.loads((TESTS / "vectors.json").read_text(encoding="utf-8"))
EXAMPLES = json.loads((TESTS / "examples.json").read_text(encoding="utf-8"))

_NUID = pwd.getpwnam("nobody").pw_uid
_NGID = grp.getgrnam("nogroup").gr_gid


def _chown_r(path, uid, gid):
    """Recursively chown a tree (path itself plus everything under it)."""
    os.chown(path, uid, gid)
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            try:
                os.chown(os.path.join(root, name), uid, gid)
            except FileNotFoundError:
                pass


def _build_env():
    """Environment for a `g++` run as nobody: writable HOME and TMPDIR (for the
    compiler's intermediate files) with the toolchain on PATH."""
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": NOBODY_HOME,
        "TMPDIR": NOBODY_HOME + "/tmp",
    }


def _prepare_nobody_dirs():
    """(Re)create the nobody-owned build/home directories used by the compile."""
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    for sub in ("", "tmp"):
        os.makedirs(os.path.join(NOBODY_HOME, sub) if sub else NOBODY_HOME, exist_ok=True)
    _chown_r(BUILD_DIR, _NUID, _NGID)
    _chown_r(NOBODY_HOME, _NUID, _NGID)


@pytest.fixture(scope="session", autouse=True)
def harden_and_build():
    """Lock the answer key, then compile the resolver from /app as ``nobody``.

    Runs as root at verify time. First the answer files are chmod 0600 / chown
    root so no unprivileged process can read them. Then the graded binary is
    compiled from the agent's source while running as ``nobody`` (writable HOME and
    TMPDIR, a nobody-owned output dir; /app made world-readable) so the compile
    itself has no access to /tests. The same unprivileged user runs every graded
    case.
    """
    # (a) Lock the answer files FIRST, before any compile or run.
    for name in ANSWER_FILES:
        p = pathlib.Path(name)
        if p.exists():
            os.chown(name, 0, 0)
            os.chmod(name, 0o600)

    # (b) Compile as nobody: give it writable caches and a readable source tree.
    _prepare_nobody_dirs()
    subprocess.run(["chmod", "-R", "a+rX", APP], check=False)
    subprocess.run(["rm", "-f", BINARY], check=False)
    proc = subprocess.run(
        ["g++", "-O2", "-std=c++17", SOURCE, "-o", BINARY],
        cwd=APP,
        capture_output=True,
        text=True,
        timeout=300,
        user="nobody",
        group="nogroup",
        env=_build_env(),
    )
    assert proc.returncode == 0, f"build (as nobody) failed: {proc.stderr[:1500]}"
    assert pathlib.Path(BINARY).exists(), "binary was not produced"
    yield BINARY


def _run(cases):
    """Run the graded binary as the unprivileged user over a list of cases.

    stdin is delivered via ``input=`` (never /dev/stdin, which nobody cannot open)
    and the process runs as ``nobody`` so it cannot read the locked answer key.
    """
    payload = json.dumps(cases)
    return subprocess.run(
        [BINARY],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
        user="nobody",
        group="nogroup",
        env={"PATH": "/usr/bin:/bin", "HOME": NOBODY_HOME},
    )


def _corpus_results(corpus):
    cases = [{"registry": c["registry"], "requirements": c["requirements"]} for c in corpus]
    proc = _run(cases)
    assert proc.returncode == 0, (
        f"program exited with {proc.returncode}; stderr: {proc.stderr[:800]}"
    )
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"stdout is not valid JSON ({exc}); got: {proc.stdout[:800]!r}")
    assert isinstance(out, list), "output must be a JSON array"
    assert len(out) == len(corpus), f"expected {len(corpus)} results, got {len(out)}"
    assert all(isinstance(x, dict) for x in out), "each result must be a JSON object"
    return out


def test_build_time_answer_key_is_unreadable(harden_and_build):
    """A build/generate step running as the build user cannot read the answer key.

    Emulates the reward-hack vector: a C++ source (as a build could embed, or a
    code generator could run) that opens /tests/vectors.json is compiled and
    executed entirely as ``nobody``. It must be denied, so no build step can bake
    the expected results into a binary.
    """
    probe = os.path.join(BUILD_DIR, "probe")
    os.makedirs(probe, exist_ok=True)
    pathlib.Path(probe, "probe.cpp").write_text(
        "#include <fstream>\n"
        "#include <iostream>\n"
        "#include <sstream>\n"
        "int main() {\n"
        '    std::ifstream f("/tests/vectors.json");\n'
        '    if (!f) { std::cout << "DENIED"; return 0; }\n'
        "    std::stringstream ss; ss << f.rdbuf();\n"
        '    std::cout << "READ:" << ss.str().size();\n'
        "    return 0;\n"
        "}\n",
        encoding="utf-8",
    )
    _chown_r(probe, _NUID, _NGID)
    build = subprocess.run(
        ["g++", "-O2", "-std=c++17", os.path.join(probe, "probe.cpp"),
         "-o", os.path.join(probe, "probe")],
        cwd=probe, capture_output=True, text=True, timeout=300,
        user="nobody", group="nogroup", env=_build_env(),
    )
    assert build.returncode == 0, f"probe build failed: {build.stderr[:800]}"
    run = subprocess.run(
        [os.path.join(probe, "probe")],
        capture_output=True, text=True, timeout=30,
        user="nobody", group="nogroup",
        env={"PATH": "/usr/bin:/bin", "HOME": NOBODY_HOME},
    )
    assert run.stdout.strip() == "DENIED", (
        f"build user could read the answer key: {run.stdout!r} {run.stderr[:400]!r}"
    )


@pytest.fixture(scope="session")
def vector_results(harden_and_build):
    """Run the program once over the hidden graded corpus."""
    return _corpus_results(VECTORS)


@pytest.fixture(scope="session")
def example_results(harden_and_build):
    """Run the program once over the published example fixtures."""
    return _corpus_results(EXAMPLES)


def test_empty_input(harden_and_build):
    """An empty list of cases must produce an empty JSON array."""
    proc = _run([])
    assert proc.returncode == 0, f"stderr: {proc.stderr[:400]}"
    assert json.loads(proc.stdout) == []


@pytest.mark.parametrize(
    "idx",
    range(len(VECTORS)),
    ids=[f"{c['family']}::{i}" for i, c in enumerate(VECTORS)],
)
def test_vector(vector_results, idx):
    """Each hidden-corpus vector (identified as ``family::idx``) must produce an
    install set and conflict records equal to the reference ground truth, so a
    failure pinpoints the specific resolution family — caret, tilde, comparators,
    transitive, backtrack, conflict, pre-release, yanked, orphan-drop, and the
    other families — whose target behaviour is mishandled."""
    case = VECTORS[idx]
    expected = case["expected"]
    got = vector_results[idx]
    assert got == expected, (
        f"requirements {case['requirements']!r}: expected {expected}, got {got}"
    )


@pytest.mark.parametrize(
    "idx",
    range(len(EXAMPLES)),
    ids=[f"example::{i}" for i in range(len(EXAMPLES))],
)
def test_example(example_results, idx):
    """Each published example fixture must resolve to its documented result."""
    case = EXAMPLES[idx]
    expected = case["expected"]
    got = example_results[idx]
    assert got == expected, (
        f"example requirements {case['requirements']!r}: expected {expected}, got {got}"
    )

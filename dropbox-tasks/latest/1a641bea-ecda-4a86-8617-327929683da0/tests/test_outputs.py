"""Behavioral verifier for the feature-bundle install-set resolver.

Builds the program from the source in /app and runs it over a hidden corpus of
resolution cases plus the graded example fixtures, checking each case's install
set and conflict records against the reference ground truth. Every case is scored
independently so a partial implementation is caught on the specific behaviours it
gets wrong.

The answer files are locked to root-only and BOTH the build and every graded run
happen as the unprivileged ``nobody`` user. Because the candidate controls the
source, building as root would let a build step (an annotation processor or other
compile-time hook the candidate ships) read the locked answer key and bake the
expected results into the class files; compiling as ``nobody`` with the answer
files unreadable closes that hole.
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
BUILD_DIR = "/tmp/bundle-build"          # nobody-owned build output dir
CLASSDIR = BUILD_DIR + "/classes"        # hermetic classes dir (owned by nobody)
NOBODY_HOME = "/tmp/nobody-home"         # nobody-writable HOME / TMPDIR
ANSWER_FILES = ("/tests/vectors.json", "/tests/examples.json")

JAVA_HOME = os.environ.get("JAVA_HOME", "/opt/java/openjdk")
JAVA = os.path.join(JAVA_HOME, "bin", "java")
JAVAC = os.path.join(JAVA_HOME, "bin", "javac")
RUN_CMD = [JAVA, "-Xint", "-XX:+UseSerialGC", "-XX:-UsePerfData", "-cp", CLASSDIR, "Main"]

VECTORS = json.loads(pathlib.Path("/tests/vectors.json").read_text(encoding="utf-8"))
EXAMPLES = json.loads(pathlib.Path("/tests/examples.json").read_text(encoding="utf-8"))

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
    """Environment for a ``javac`` run as nobody: writable HOME and TMPDIR, the
    JDK on PATH, no network."""
    return {
        "PATH": os.path.join(JAVA_HOME, "bin") + ":/usr/local/bin:/usr/bin:/bin",
        "HOME": NOBODY_HOME,
        "JAVA_HOME": JAVA_HOME,
        "TMPDIR": NOBODY_HOME + "/tmp",
    }


def _run_env():
    """Environment for a graded ``java`` run as nobody."""
    return {
        "PATH": os.path.join(JAVA_HOME, "bin") + ":/usr/bin:/bin",
        "HOME": NOBODY_HOME,
        "TMPDIR": NOBODY_HOME + "/tmp",
    }


def _prepare_nobody_dirs():
    """(Re)create the nobody-owned build/home directories."""
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    os.makedirs(CLASSDIR, exist_ok=True)
    for sub in ("", "tmp"):
        os.makedirs(os.path.join(NOBODY_HOME, sub) if sub else NOBODY_HOME, exist_ok=True)
    _chown_r(BUILD_DIR, _NUID, _NGID)
    _chown_r(NOBODY_HOME, _NUID, _NGID)


@pytest.fixture(scope="session", autouse=True)
def _harden_and_build():
    """Lock the answer key, then compile the resolver from /app as ``nobody``.

    Runs as root at verify time. First the answer files are chmod 0600 / chown
    root so no unprivileged process can read them. Then the graded classes are
    compiled from the candidate's source while running as ``nobody`` (writable
    HOME and TMPDIR, a nobody-owned classes dir; /app made world-readable) so the
    build itself has no access to /tests. The same unprivileged user runs every
    graded case. Compilation happens once for the whole session; each graded run
    only launches the already-built ``java`` program.
    """
    # (a) Lock the answer files FIRST, before any build or run.
    for name in ANSWER_FILES:
        p = pathlib.Path(name)
        if p.exists():
            os.chown(name, 0, 0)
            os.chmod(name, 0o600)

    # (b) Compile as nobody: give it writable caches and a readable source tree.
    _prepare_nobody_dirs()
    subprocess.run(["chmod", "-R", "a+rX", APP], check=False)
    proc = subprocess.run(
        [JAVAC, "-d", CLASSDIR, os.path.join(APP, "Main.java")],
        cwd=APP,
        capture_output=True,
        text=True,
        timeout=300,
        user="nobody",
        group="nogroup",
        env=_build_env(),
    )
    assert proc.returncode == 0, f"compile (as nobody) failed: {proc.stderr[:1500]}"
    assert pathlib.Path(CLASSDIR, "Main.class").exists(), "Main.class was not produced"
    yield


def _run(cases):
    """Run the graded program as the unprivileged user over a list of cases.

    stdin is delivered via ``input=`` (never /dev/stdin, which nobody cannot open)
    and the process runs as ``nobody`` so it cannot read the locked answer key.
    """
    payload = json.dumps([{"registry": c["registry"], "requirements": c["requirements"]} for c in cases])
    return subprocess.run(
        RUN_CMD,
        input=payload,
        capture_output=True,
        text=True,
        timeout=120,
        user="nobody",
        group="nogroup",
        env=_run_env(),
    )


def test_build_time_answer_key_is_unreadable(_harden_and_build):
    """A build/generate step running as the build user cannot read the answer key.

    Emulates the reward-hack vector: a Java source (as a compile-time hook or the
    program itself could embed) that opens /tests/vectors.json is compiled and
    executed entirely as ``nobody``. It must be denied, so no build step can bake
    the expected results into the class files.
    """
    probe = os.path.join(BUILD_DIR, "probe")
    os.makedirs(probe, exist_ok=True)
    pathlib.Path(probe, "Probe.java").write_text(
        "import java.nio.file.Files;\n"
        "import java.nio.file.Paths;\n"
        "public class Probe {\n"
        "    public static void main(String[] a) {\n"
        "        try {\n"
        "            byte[] b = Files.readAllBytes(Paths.get(\"/tests/vectors.json\"));\n"
        "            System.out.print(\"READ:\" + b.length);\n"
        "        } catch (Exception e) {\n"
        "            System.out.print(\"DENIED\");\n"
        "        }\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )
    _chown_r(probe, _NUID, _NGID)
    build = subprocess.run(
        [JAVAC, "-d", probe, os.path.join(probe, "Probe.java")],
        cwd=probe, capture_output=True, text=True, timeout=300,
        user="nobody", group="nogroup", env=_build_env(),
    )
    assert build.returncode == 0, f"probe build failed: {build.stderr[:800]}"
    run = subprocess.run(
        [JAVA, "-cp", probe, "Probe"],
        capture_output=True, text=True, timeout=30,
        user="nobody", group="nogroup", env=_run_env(),
    )
    assert run.stdout.strip() == "DENIED", (
        f"build user could read the answer key: {run.stdout!r} {run.stderr[:400]!r}"
    )


@pytest.fixture(scope="session")
def vector_results(_harden_and_build):
    """Run the program once over the hidden corpus and return its parsed output."""
    proc = _run(VECTORS)
    assert proc.returncode == 0, (
        f"program exited with {proc.returncode}; stderr: {proc.stderr[:800]}"
    )
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"stdout is not valid JSON ({exc}); got: {proc.stdout[:800]!r}")
    assert isinstance(out, list), "output must be a JSON array"
    assert len(out) == len(VECTORS), f"expected {len(VECTORS)} results, got {len(out)}"
    assert all(isinstance(x, dict) for x in out), "each result must be a JSON object"
    return out


@pytest.fixture(scope="session")
def example_results(_harden_and_build):
    """Run the program once over the graded example fixtures and parse its output."""
    proc = _run(EXAMPLES)
    assert proc.returncode == 0, (
        f"program exited with {proc.returncode}; stderr: {proc.stderr[:800]}"
    )
    out = json.loads(proc.stdout)
    assert isinstance(out, list) and len(out) == len(EXAMPLES)
    return out


def test_empty_input(_harden_and_build):
    """An empty list of cases must produce an empty JSON array."""
    proc = _run([])
    assert proc.returncode == 0, f"stderr: {proc.stderr[:400]}"
    assert json.loads(proc.stdout) == []


@pytest.mark.parametrize(
    "idx",
    range(len(VECTORS)),
    ids=[f"{c['family']}::{i}" for i, c in enumerate(VECTORS)],
)
def test_case(vector_results, idx):
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
    """Each graded example fixture must resolve to its documented result."""
    case = EXAMPLES[idx]
    expected = case["expected"]
    got = example_results[idx]
    assert got == expected, (
        f"example requirements {case['requirements']!r}: expected {expected}, got {got}"
    )

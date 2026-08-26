"""Behavioral verifier for the version-selector matcher task.

A Kotlin CLI is compiled from /app and invoked once per case as java -jar selgate.jar <version> <selector>.

Its single line of stdout must equal, byte for byte, "true" or "false" (plus a
trailing newline) according to whether the version satisfies the Gradle version
selector.

Ground truth was baked at authoring time by driving Gradle's own dependency
version-selection code -- DefaultVersionSelectorScheme.parseSelector(selector)
followed by VersionSelector.accept(version), backed by the real
DefaultVersionComparator / VersionParser -- over a large, quirk-biased corpus of
(version, selector) pairs and recording its boolean answer. The frozen subset
lives in cases.json next to this file; Gradle itself and any reference source
are deliberately NOT present in the task image, so the program must reproduce
Gradle's semantics from the specification rather than reading or porting it.

The corpus is biased toward the parts of Gradle's version-selection language
where independent reimplementations most often diverge from the real tool: the
special-qualifier ordering (dev < ... < rc < snapshot < final < ga < release <
sp, with unknown qualifiers ordered among themselves), numeric-versus-string
part comparison and unequal-length tie-breaks, the range forms "[a,b)" /
"(,b]" / "[a,)" with their inclusive/exclusive bounds, the exclusive-upper
prefix rule, the "1.+" / "1.2.+" sub-version prefixes, the bare "+" selector,
and the "latest.release" / "latest.integration" dynamic selectors. Cases are
grouped into families by which feature they exercise and parametrized per case,
so no single monolithic test carries all of them and any correlated blind spot
surfaces as a cluster of failures.
"""
import json
import os
import re
import subprocess

import pytest

APP = "/app"
JAR = os.path.join(APP, "selgate.jar")
CASES_PATH = os.path.join(os.path.dirname(__file__), "cases.json")


def _build():
    """Compile the current /app source so the verifier tests the agent's code."""
    subprocess.run(
        ["kotlinc", os.path.join(APP, "Selgate.kt"), "-include-runtime", "-d", JAR],
        check=True, capture_output=True, text=True)


_build()


with open(CASES_PATH) as _f:
    _CASES = json.load(_f)


def _run(version, selector):
    """Invoke the built binary; return (returncode, stdout)."""
    out = subprocess.run(
        ["java", "-Xint", "-XX:+UseSerialGC", "-jar", JAR, version, selector],
        capture_output=True, text=True, timeout=20)
    return out.returncode, out.stdout


def _check(version, selector, expected):
    """Assert the binary's decision matches Gradle for one case."""
    want = "true" if expected else "false"
    rc, got = _run(version, selector)
    assert rc == 0, (
        "expected success for satisfies(%r, %r) but binary exited %d"
        % (version, selector, rc))
    assert got.endswith("\n"), (
        "output for satisfies(%r, %r) must end with a single newline, got %r"
        % (version, selector, got))
    assert got.count("\n") == 1, (
        "output for satisfies(%r, %r) must be exactly one line, got %r"
        % (version, selector, got))
    assert got.rstrip("\n") == want, (
        "satisfies(%r, %r): want %r got %r"
        % (version, selector, want, got.rstrip("\n")))


# --- Family classification ------------------------------------------------

def _family(version, selector):
    s = selector.strip()
    if s == "+":
        return "plus"
    if s in ("latest.release", "latest.integration"):
        return "latest"
    if s.endswith("+"):
        return "subversion"
    if s[:1] in "[(" and "," in s:
        inner = s[1:-1]
        return "range_qual" if re.search(r"[A-Za-z]", inner) else "range_num"
    if re.search(r"[A-Za-z]", s):
        return "exact_qual"
    return "exact_num"


def _sanitize(s):
    keep = [ch if ch.isalnum() else "_" for ch in s]
    return ("".join(keep) or "empty")[:40]


def _params(family):
    out = []
    for i, c in enumerate(_CASES):
        if _family(c["version"], c["selector"]) == family:
            cid = "%s-%d-%s-%s" % (family, i, _sanitize(c["version"]),
                                   _sanitize(c["selector"]))
            out.append(pytest.param(c["version"], c["selector"], c["expected"],
                                    id=cid))
    return out


@pytest.mark.parametrize("version,selector,expected", _params("exact_num"))
def test_exact_numeric(version, selector, expected):
    """A bare numeric selector matches only versions that compare equal after
    Gradle's part splitting and unequal-length tie-break."""
    _check(version, selector, expected)


@pytest.mark.parametrize("version,selector,expected", _params("exact_qual"))
def test_exact_qualifier(version, selector, expected):
    """A bare selector carrying a qualifier (dev/rc/final/... or an unknown
    word, in any case) matches only versions that compare exactly equal under
    the special-qualifier ordering and numeric-vs-string part rules."""
    _check(version, selector, expected)


@pytest.mark.parametrize("version,selector,expected", _params("range_num"))
def test_range_numeric(version, selector, expected):
    """Numeric range selectors [a,b) / (,b] / [a,) admit a version iff it lies
    within the (in/ex)clusive bounds, including the exclusive-upper prefix
    rule."""
    _check(version, selector, expected)


@pytest.mark.parametrize("version,selector,expected", _params("range_qual"))
def test_range_qualifier(version, selector, expected):
    """Range selectors whose bounds carry qualifiers exercise the special-
    qualifier ordering inside bound comparisons."""
    _check(version, selector, expected)


@pytest.mark.parametrize("version,selector,expected", _params("subversion"))
def test_subversion_prefix(version, selector, expected):
    """The '1.+' / '1.2.+' sub-version prefix admits exactly the versions whose
    text begins with the literal prefix up to the '+'."""
    _check(version, selector, expected)


@pytest.mark.parametrize("version,selector,expected", _params("plus"))
def test_plus(version, selector, expected):
    """The bare '+' selector admits every version."""
    _check(version, selector, expected)


@pytest.mark.parametrize("version,selector,expected", _params("latest"))
def test_latest(version, selector, expected):
    """The dynamic 'latest.release' / 'latest.integration' selectors, evaluated
    against a single candidate without component metadata, admit the version."""
    _check(version, selector, expected)


@pytest.mark.parametrize(
    "version,selector,expected",
    [
        ("1.0.0", "1.0.0", True),
        ("1.0.1", "1.0.0", False),
        ("1.5.0", "[1.0,2.0)", True),
        ("2.0.0", "[1.0,2.0)", False),
        ("0.5.0", "(,1.0]", True),
        ("1.0.0", "(,1.0]", False),
        ("5.0.0", "[1.0,)", True),
        ("1.2.3", "1.+", True),
        ("2.0.0", "1.+", False),
        ("1", "1.+", False),
        ("10", "1.+", False),
        ("1.2.5", "1.2.+", True),
        ("1.3.0", "1.2.+", False),
        ("1.0.0", "+", True),
        ("1.0.0-SNAPSHOT", "latest.release", True),
        ("1.0.0", "latest.integration", True),
        # special-qualifier ordering inside a range bound
        ("1.0.0-rc", "[1.0.0-dev,)", True),
        ("1.0.0-dev", "[1.0.0-rc,)", False),
        ("1.0.0", "[1.0.0-sp,)", True),
        # extra string part orders below the release
        ("1.0.0-final", "[1.0.0,)", False),
        # numeric extra part orders above the release
        ("1.0.0.5", "[1.0.0,)", True),
        # exclusive-upper prefix rule: 3.ga starts with "3", so it is excluded
        ("3.ga", "(,3)", False),
        ("3.ga", "(,3]", True),
        # equal special meaning across case treats versions as equal
        ("RC.beta.3.15", "[rc,)", True),
        # numeric outranks non-numeric at the same position
        ("1.0.a", "[1.0.0,)", False),
    ],
)
def test_known_anchors(version, selector, expected):
    """Hand-verified anchor cases pinning the trickiest divergences so a
    regression fails loudly and readably."""
    _check(version, selector, expected)

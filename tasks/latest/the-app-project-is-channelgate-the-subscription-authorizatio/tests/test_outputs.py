"""Behavioral checks for sensor bus channel admission."""

import json
import os
import random
import re
import subprocess
import tempfile

import pytest

APP_DIR = os.environ.get("APP_DIR", "/app")
ALPHA = "abc"
RUN_TIMEOUT = 60
N_ADV = 400
N_ADV_SCALED = 800
N_ADV_REF = 40
N_ADV_INNER = 60
_PREPARED = {}


def _child_env():
    """Give the candidate a scrubbed environment so it cannot read verifier state."""
    keep = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL")
    return {k: os.environ[k] for k in keep if k in os.environ}


@pytest.fixture(scope="session")
def program():
    """Rebuild the gate from /app source and hand back the command that runs it."""
    if "cmd" in _PREPARED:
        return _PREPARED["cmd"]
    binary = os.path.join(APP_DIR, "channelgate")
    subprocess.run(["make", "-C", APP_DIR, "clean"], capture_output=True, text=True,
                   timeout=RUN_TIMEOUT)
    assert not os.path.exists(binary), "clean left a stale binary behind"
    build = subprocess.run(["make", "-C", APP_DIR], capture_output=True, text=True,
                           timeout=RUN_TIMEOUT * 6)
    assert build.returncode == 0, "build failed:\n" + build.stdout + "\n" + build.stderr
    assert os.path.exists(binary), "build produced no binary"
    _PREPARED["cmd"] = [binary]
    return _PREPARED["cmd"]


def _run(program, requests):
    """Feed one batch to the candidate and return its admitted list."""
    payload = json.dumps({"requests": requests})
    proc = subprocess.run(
        program, input=payload, capture_output=True, text=True,
        timeout=RUN_TIMEOUT, env=_child_env(), cwd=tempfile.gettempdir(),
    )
    assert proc.returncode == 0, "program exited non-zero:\n" + proc.stderr
    data = json.loads(proc.stdout)
    res = data["admitted"]
    assert len(res) == len(requests), "result count mismatch"
    return res


def _ref(requests):
    """Reference decisions for non-adversarial rules only."""
    out = []
    for c in requests:
        try:
            out.append(re.fullmatch(c["rule"], c["channel"]) is not None)
        except re.error:
            out.append(False)
    return out


# --- rule generator ---

def _class(rng):
    """Build one bracketed byte class, sometimes negated, sometimes a range."""
    chars = "".join(sorted(rng.sample(ALPHA, rng.randint(1, 2))))
    body = "a-c" if rng.random() < 0.3 else chars
    if rng.random() < 0.4:
        body = "^" + body
    return "[" + body + "]"


def _quant(rng):
    """Pick a quantifier suffix, or none at all."""
    r = rng.random()
    if r < 0.45:
        return ""
    if r < 0.62:
        return rng.choice(["*", "+", "?"])
    lo = rng.randint(0, 2)
    r2 = rng.random()
    if r2 < 0.4:
        return "{%d}" % lo
    if r2 < 0.7:
        return "{%d,}" % lo
    return "{%d,%d}" % (lo, lo + rng.randint(0, 2))


def _simple_sub(rng, depth):
    """Assemble a short reference-free fragment, occasionally with a branch."""
    def atom():
        """Draw one single-byte term."""
        r = rng.random()
        if r < 0.5:
            return rng.choice(ALPHA)
        if r < 0.72:
            return "."
        return _class(rng)

    s = "".join(atom() + _quant(rng) for _ in range(rng.randint(1, 3)))
    if depth > 0 and rng.random() < 0.3:
        s = s + "|" + _simple_sub(rng, depth - 1)
    return s


def _slow_unit(rng):
    """Assemble a group whose body and wrapper are both repeated."""
    if rng.random() < 0.5:
        inner = "".join(rng.choice(ALPHA) for _ in range(rng.randint(1, 2)))
    else:
        inner = _class(rng)
    inner += rng.choice(["+", "*", "{1,2}", "{1,3}"])
    return "(" + inner + ")" + rng.choice(["+", "*", "{1,2}"])


def _gen_rule(rng):
    """Stitch two to five segments into one rule, wiring references to groups already opened."""
    ngroups = 0
    eligible = []
    segs = []
    for _ in range(rng.randint(2, 5)):
        r = rng.random()
        if r < 0.30:
            ngroups += 1
            segs.append("(" + _simple_sub(rng, 1) + ")")
            eligible.append(ngroups)
        elif r < 0.45 and eligible:
            segs.append("\\%d" % rng.choice(eligible))
        elif r < 0.62:
            ngroups += 1
            segs.append(_slow_unit(rng))
        else:
            base = _class(rng) if rng.random() < 0.35 else rng.choice(ALPHA + ".")
            segs.append(base + _quant(rng))
    return "".join(segs)


def _make_requests(n, seed):
    """Draw n rule and channel pairs from a fixed seed."""
    rng = random.Random(seed)
    requests = []
    while len(requests) < n:
        rule = _gen_rule(rng)
        try:
            re.compile(rule)
        except re.error:
            continue
        channel = "".join(rng.choice(ALPHA) for _ in range(rng.randint(0, 10)))
        requests.append({"rule": rule, "channel": channel})
    return requests


# --- correctness ---

@pytest.mark.parametrize("seed", [11, 23, 47, 88, 131, 199, 277, 314])
def test_reference_decisions(program, seed):
    """Every generated rule keeps its whole-channel accept or reject decision."""
    requests = _make_requests(250, seed)
    got = _run(program, requests)
    exp = _ref(requests)
    diffs = [(c["rule"], c["channel"], g, e)
             for c, g, e in zip(requests, got, exp) if g != e]
    assert not diffs, "decision disagreements: %r" % diffs[:10]


CAPTURE_REFERENCE_CASES = [
    ("literal_repeat", {"rule": "(abc)\\1", "channel": "abcabc"}),
    ("literal_repeat_short", {"rule": "(abc)\\1", "channel": "abcab"}),
    ("dot_repeat", {"rule": "(a.c)\\1", "channel": "abcabc"}),
    ("dot_repeat_mismatch", {"rule": "(a.c)\\1", "channel": "abcadc"}),
    ("alt_short", {"rule": "(a|bb)c\\1", "channel": "aca"}),
    ("alt_long", {"rule": "(a|bb)c\\1", "channel": "bbcbb"}),
    ("star_capture", {"rule": "(a*)b\\1", "channel": "aabaa"}),
    ("star_capture_mismatch", {"rule": "(a*)b\\1", "channel": "aabaaa"}),
    ("two_groups_palindrome", {"rule": "(.)(.)\\2\\1", "channel": "abba"}),
    ("two_groups_mismatch", {"rule": "(.)(.)\\2\\1", "channel": "abab"}),
    ("optional_inside_group", {"rule": "x(ab?)y\\1", "channel": "xabyab"}),
    ("optional_inside_group_mismatch", {"rule": "x(ab?)y\\1", "channel": "xayb"}),
    ("nested_repetition_capture", {"rule": "((a+)+)b\\1", "channel": "aaabaaa"}),
    ("nested_repetition_capture_mismatch", {"rule": "((a+)+)b\\1", "channel": "aaabaa"}),
    ("counted_repetition_capture", {"rule": "((a{1,2})+)b\\1", "channel": "aaabaaa"}),
    ("ambiguous_alternation_capture", {"rule": "((a|aa)*)b\\1", "channel": "aaabaaa"}),
    ("nested_optional_group", {"rule": "((a(b)?)+)c\\1", "channel": "ababcabab"}),
    ("nested_optional_group_mismatch", {"rule": "((a(b)?)+)c\\1", "channel": "ababcaba"}),
]


@pytest.mark.parametrize("name,case", CAPTURE_REFERENCE_CASES,
                         ids=[x[0] for x in CAPTURE_REFERENCE_CASES])
def test_capture_reference_rule_preserved(program, name, case):
    """A rule reading back an earlier capture keeps its original decision."""
    got = _run(program, [case])
    exp = _ref([case])
    assert got == exp, "%s disagreed: got %r expected %r" % (name, got, exp)


INVALID_RULE_CASES = [
    ("dangling_escape", {"rule": "abc\\", "channel": "abc"}),
    ("unclosed_group", {"rule": "(abc", "channel": "abc"}),
    ("unclosed_class", {"rule": "[abc", "channel": "a"}),
    ("bare_quantifier", {"rule": "*abc", "channel": "abc"}),
]


@pytest.mark.parametrize("name,case", INVALID_RULE_CASES,
                         ids=[x[0] for x in INVALID_RULE_CASES])
def test_invalid_rule_reports_false(program, name, case):
    """A rule that cannot be read is denied without aborting the batch."""
    assert _run(program, [case]) == [False], name


# --- resource exhaustion: the search space, not the clock ---

CPU_EXHAUSTION = [
    ("(a+)+", "a" * N_ADV + "b"),
    ("(a*)*", "a" * N_ADV + "b"),
    ("(a|a)*", "a" * N_ADV + "b"),
    ("(aa|a)*", "a" * N_ADV + "b"),
    ("((a)*)*", "a" * N_ADV + "b"),
    ("(a+)+(b+)+", "a" * (N_ADV // 2) + "b" * (N_ADV // 2) + "c"),
    ("(.*)*c", "a" * N_ADV + "b"),
    ("(a|ab)*", "a" * N_ADV + "c"),
    ("(a{1,2})+", "a" * N_ADV + "b"),
    ("(a{1,3}){1,3}", "a" * N_ADV + "b"),
    ("([ab]+)+", "a" * N_ADV + "c"),
    ("([ab]{1,2})*", "a" * N_ADV + "c"),
    ("([a-c]*)*d", "a" * N_ADV + "e"),
]


def test_no_cpu_exhaustion_search(program):
    """Ambiguous repetition over a long rejected channel still returns a decision."""
    requests = [{"rule": p, "channel": t} for p, t in CPU_EXHAUSTION]
    got = _run(program, requests)
    exp = [False] * len(requests)
    diffs = [(c["rule"], len(c["channel"]), g, e)
             for c, g, e in zip(requests, got, exp) if g != e]
    assert not diffs, "decision disagreements on adversarial inputs: %r" % diffs


CPU_EXHAUSTION_WITH_CAPREF = [
    ("(x)(a+)+\\1", "x" + "a" * N_ADV_REF + "y"),
    ("(z)(a|a)*\\1", "z" + "a" * N_ADV_REF + "y"),
    ("(ab)(c+)+(d+)+\\1", "ab" + "c" * (N_ADV_REF // 2) + "d" * (N_ADV_REF // 2) + "e"),
    ("(p)(.*)*q\\1", "p" + "a" * N_ADV_REF + "b"),
    ("(mn)(a+)+(a+)+\\1", "mn" + "a" * N_ADV_REF + "z"),
    ("(x)(a{1,2})+\\1", "x" + "a" * N_ADV_REF + "y"),
    ("(y)([ab]+)+\\1", "y" + "a" * N_ADV_REF + "c"),
    ("(w)([a-c]{1,3}){1,3}q\\1", "w" + "a" * N_ADV_REF + "z"),
]

CPU_EXHAUSTION_REFERENCED_CAPTURE = [
    ("((a+)+)b\\1", "a" * N_ADV_REF + "c"),
    ("((a|aa)*)b\\1", "a" * N_ADV_REF + "c"),
    ("(([ab]+)+)c\\1", "a" * N_ADV_REF + "d"),
    ("((a{1,2})+)b\\1", "a" * N_ADV_INNER + "c"),
    ("(([a-c]*)*)d\\1", "a" * N_ADV_REF + "e"),
]


def test_no_cpu_exhaustion_search_with_capture_ref(program):
    """A capture reference beside an ambiguous subexpression still returns a decision."""
    requests = [{"rule": p, "channel": t} for p, t in CPU_EXHAUSTION_WITH_CAPREF]
    got = _run(program, requests)
    exp = [False] * len(requests)
    diffs = [(c["rule"], len(c["channel"]), g, e)
             for c, g, e in zip(requests, got, exp) if g != e]
    assert not diffs, "decision disagreements on adversarial capture-reference inputs: %r" % diffs


def test_no_cpu_exhaustion_search_inside_referenced_capture(program):
    """A referenced capture produced by an ambiguous subexpression still returns a decision."""
    requests = [{"rule": p, "channel": t} for p, t in CPU_EXHAUSTION_REFERENCED_CAPTURE]
    got = _run(program, requests)
    exp = [False] * len(requests)
    diffs = [(c["rule"], len(c["channel"]), g, e)
             for c, g, e in zip(requests, got, exp) if g != e]
    assert not diffs, "decision disagreements on referenced-capture inputs: %r" % diffs


def test_no_cpu_exhaustion_search_scaled(program):
    """The same shapes at a larger size stay decidable, so the win is not a constant factor."""
    requests = [{"rule": "(a+)+", "channel": "a" * N_ADV_SCALED + "b"},
                {"rule": "(a*)*", "channel": "a" * N_ADV_SCALED + "b"},
                {"rule": "(a|a)*b", "channel": "a" * N_ADV_SCALED + "c"},
                {"rule": "(a{1,2})+", "channel": "a" * N_ADV_SCALED + "b"},
                {"rule": "([ab]+)+", "channel": "a" * N_ADV_SCALED + "c"}]
    got = _run(program, requests)
    exp = [False] * len(requests)
    diffs = [(c["rule"], len(c["channel"]), g, e)
             for c, g, e in zip(requests, got, exp) if g != e]
    assert not diffs, "decision disagreements: %r" % diffs


ADMITTED_ADVERSARIAL = [
    ("(a+)+", "a"),
    ("(a+)+", "a" * 40),
    ("(a+)+", "a" * 200),
    ("(a+)+", "a" * N_ADV),
    ("(a*)*", "a" * 200),
    ("(a|a)*", "a" * N_ADV),
    ("(aa|a)*", "a" * 200),
    ("([ab]+)+", "ab" * 100),
    ("([ab]+)+", "ab" * (N_ADV // 2)),
    ("(a{1,2})+", "a" * N_ADV),
    ("([a-c]*)*d", "a" * 200 + "d"),
    ("(x)(a+)+\\1", "x" + "a" * N_ADV_REF + "x"),
    ("((a+)+)b\\1", "a" * N_ADV_INNER + "b" + "a" * N_ADV_INNER),
    ("(y)([ab]+)+\\1", "y" + "ab" * (N_ADV_REF // 2) + "y"),
]


@pytest.mark.parametrize("rule,channel", ADMITTED_ADVERSARIAL,
                         ids=["%s_len%d" % (r, len(t)) for r, t in ADMITTED_ADVERSARIAL])
def test_adversarial_shapes_still_admit(program, rule, channel):
    """The same ambiguous shapes over channels they do cover are admitted, not denied wholesale."""
    assert _run(program, [{"rule": rule, "channel": channel}]) == [True], rule

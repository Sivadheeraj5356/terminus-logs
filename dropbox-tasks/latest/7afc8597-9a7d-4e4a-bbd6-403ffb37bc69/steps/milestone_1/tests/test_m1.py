import json
import os
import re
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import refregex

APP = "/app"
BIN = os.path.join(APP, "target", "release", "rsx")


def build_once():
    if os.path.exists(BIN):
        return
    subprocess.run(
        ["cargo", "build", "--release"],
        cwd=APP,
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="module", autouse=True)
def _build():
    build_once()
    assert os.path.exists(BIN), "rsx binary was not produced"


def run_compile(pattern):
    return subprocess.run(
        [BIN, "compile", pattern],
        capture_output=True,
    )


def parse_dfa(text):
    lines = text.split("\n")
    assert lines and lines[-1] == "", "output must end with a single trailing newline"
    lines = lines[:-1]
    assert lines[0].startswith("states "), "missing states header"
    n = int(lines[0].split(" ", 1)[1])
    assert lines[1] == "start 0", "start line must be 'start 0'"
    assert lines[2] == "accept" or lines[2].startswith("accept "), "missing accept line"
    if lines[2] == "accept":
        accept = set()
    else:
        accept = set(int(x) for x in lines[2].split(" ")[1:])
    state_lines = lines[3:]
    assert len(state_lines) == n, "must print exactly one line per state"
    trans = [dict() for _ in range(n)]
    for sid in range(n):
        ln = state_lines[sid]
        head, _, rest = ln.partition(":")
        assert int(head) == sid, "state lines must be in ascending id order"
        rest = rest.strip()
        if rest == "":
            continue
        prev_hi = -1
        for part in rest.split(";"):
            label, _, tgt = part.partition("=>")
            assert tgt == tgt.strip() and re.fullmatch(r"\d+", tgt), f"bad target {tgt!r}"
            t = int(tgt)
            if "-" in label:
                lo_s, hi_s = label.split("-")
                assert re.fullmatch(r"[0-9a-f]{2}", lo_s), f"hex must be lowercase two-digit: {lo_s!r}"
                assert re.fullmatch(r"[0-9a-f]{2}", hi_s), f"hex must be lowercase two-digit: {hi_s!r}"
                lo = int(lo_s, 16)
                hi = int(hi_s, 16)
                assert lo < hi, "range must have lo < hi (single byte must use b=>t form)"
                for b in range(lo, hi + 1):
                    trans[sid][b] = t
            else:
                assert re.fullmatch(r"[0-9a-f]{2}", label), f"hex must be lowercase two-digit: {label!r}"
                lo = hi = int(label, 16)
                trans[sid][lo] = t
            assert lo > prev_hi, "ranges within a state must be sorted ascending and non-overlapping"
            prev_hi = hi
    return n, accept, trans


def dfa_accepts(dfa, data):
    n, accept, trans = dfa
    state = 0
    for byte in data:
        nxt = trans[state].get(byte)
        if nxt is None:
            return False
        state = nxt
    return state in accept


def sample_strings():
    base = [b"", b"a", b"b", b"c", b"ab", b"abc", b"abcd", b"aa", b"aaa",
            b"aaaa", b"aaaaa", b"ba", b"bb", b"abab", b"foo", b"foobar",
            b"foobarbaz", b"0", b"9", b"00", b"123", b"0x", b"0xAB",
            b"0xabcdef", b"banana", b"bananana", b"color", b"colour",
            b"gray", b"grey", b"rhythm", b"aeiou", b"xyz", b"A", b"Z",
            b"_", b"_a1", b"1a", b"-", b"--", b"-+5", b"+", b" ", b"\t",
            b"\n", b"true", b"false", b"yes", b"no", b"maybe", b"x",
            b"xx", b"xxx", b"xxxx", b"xxxxx", b"abbbc", b"cd", b"abab"]
    # broaden byte-level coverage: high bytes, control bytes, NUL, punctuation,
    # mixed case, and every single byte value so non-canonical or wrong-alphabet
    # transitions are exercised across the full 0x00..0xff alphabet.
    extra = [b"\x00", b"\xff", b"\x7f", b"\x80", b"\x1f", b"\r\n", b"\x0b\x0c",
             b"A1b2C3", b"ABCDEF", b"abcdef", b"G", b"g", b"::", b"[]", b"{}",
             b".", b"..", b"a.c", b"a\nc", b"-_-", b"  ", b"\t\t", b"9a",
             b"deadBEEF", b"00ff", b"zzzzzz", b"AaBbCc", b"!@#", b"~`"]
    extra += [bytes([b]) for b in range(256)]  # every single byte value
    # multi-byte discriminators for class-algebra + repetition patterns so that
    # +/{m,n} closures over intersected/subtracted sets are exercised, not just
    # single-byte membership.
    extra += [b"bcd", b"aei", b"aeiou", b"abc", b"def", b"ptr", b"pqrst",
              b"BCDFG", b"AEIOU", b"mnop", b"ghij", b"0a", b"4", b"5",
              b"aeibcd", b"consonant", b"rhythm", b"ababab", b"xxy"]
    return base + extra


PATTERNS = [
    "abc", "a|b|c", "a*", "a+", "a?", "ab*c", "(ab)+", "(a|b)*c",
    "a{3}", "a{2,4}", "a{2,}", "[a-z]", "[a-z]+", "[0-9]{1,3}",
    "[[:digit:]]+", "[[:alpha:]][[:alnum:]]*", "[[:hexdigit:]]{2}",
    "[a-z--[aeiou]]+", "0x[[:hexdigit:]]+", "foo|foobar", "colou?r",
    "gr[ae]y", "[A-Za-z_][A-Za-z0-9_]*", "[^aeiou]+", "a.c", "\\.",
    "\\x41\\x42", "(foo)(bar)?", "ba(na)+", "[-+]?[0-9]+",
    "[0-9]+(\\.[0-9]+)?", "true|false", "(yes|no|maybe)", "x{0,3}",
    "x{5}", "(ab|cd){2,3}", "[[:upper:]]{2,5}", "[a-f0-9]{8}",
    "[ \t]+", "a(b|c|d)e", "ab?c?d?", "[[:punct:]]+", "[a-zA-Z]{1,10}",
    "[0-9a-fA-F]+", "cat|dog|bird", "[[:alnum:]--[[:digit:]]]+",
    "[[:alnum:]]--[[:digit:]]", "z{2,2}", "(a|b|c|d|e)", "[]",
    # harder class-algebra patterns: intersection, mixed --/&& applied strictly
    # left to right, additions layered on top of operators, nested operands,
    # negation applied once after the whole body, and empty/universal/count-zero
    # corner cases. A plausible implementation that batches all additions before
    # subtractions, gives &&/-- a precedence, or mishandles [] diverges here.
    "[a-z&&[^aeiou]]+", "[[:alpha:]&&[a-m]]+",
    "[[:alnum:]&&[[:upper:]]--[AEIOU]]+", "[a-c&&[b]d]", "[a-z--[a-m&&[a-f]]]",
    "[d-w&&[m-z]&&[p-u]]", "[b-y--[c-e]bcd]", "[b-y--[c-e]&&[a-g]]",
    "[def--[e]g&&[d-f]]", "[0-9&&[[:alpha:]]]", "[b&&[c-e]f]",
    "[b-y--[bcd]--[wxy]]", "[b-y--[b-m--[b-g]]]", "[^b-y&&[b-m]]",
    "[^[:digit:]&&[0-4]]", "a{0}bc", "x{0,2}y", "(ab){0}c", "^abc$",
    "[\\x00-\\xff]", "[]*", "[]+", "[]?", "[^]",
]


class TestMilestone1:
    def test_binary_exists(self):
        """The release binary builds and is present."""
        assert os.path.exists(BIN)

    @pytest.mark.parametrize("pat", PATTERNS)
    def test_valid_patterns_compile(self, pat):
        """Every documented valid pattern compiles with exit code 0."""
        r = run_compile(pat)
        assert r.returncode == 0, (pat, r.stderr)

    @pytest.mark.parametrize("pat", PATTERNS)
    def test_language_equivalence(self, pat):
        """The compiled DFA accepts exactly the strings the reference accepts."""
        r = run_compile(pat)
        assert r.returncode == 0, (pat, r.stderr)
        dfa = parse_dfa(r.stdout.decode("latin-1"))
        for s in sample_strings():
            expected = refregex.full_match(pat.encode("latin-1"), s)
            got = dfa_accepts(dfa, s)
            assert got == expected, (pat, s, expected, got)

    @pytest.mark.parametrize("pat", PATTERNS)
    def test_header_and_format(self, pat):
        """Output header lines and per-state ordering follow the canonical shape."""
        r = run_compile(pat)
        assert r.returncode == 0
        text = r.stdout.decode("latin-1")
        n, accept, trans = parse_dfa(text)
        assert n >= 1
        for sid in range(n):
            assert all(0 <= t < n for t in trans[sid].values())
        for a in accept:
            assert 0 <= a < n

    def test_exact_simple_outputs(self):
        """A handful of tiny patterns have exactly the hand-derived canonical form."""
        cases = {
            "abc": "states 4\nstart 0\naccept 3\n0: 61=>1\n1: 62=>2\n2: 63=>3\n3:\n",
            "a*": "states 1\nstart 0\naccept 0\n0: 61=>0\n",
            "a|b": "states 2\nstart 0\naccept 1\n0: 61-62=>1\n1:\n",
            # empty-set class: lone non-accepting start state, no transitions.
            "[]": "states 1\nstart 0\naccept\n0:\n",
            # negated empty set: matches any of the 256 bytes.
            "[^]": "states 2\nstart 0\naccept 1\n0: 00-ff=>1\n1:\n",
            # star of the empty language: one accepting start, no transitions.
            "[]*": "states 1\nstart 0\naccept 0\n0:\n",
        }
        for pat, expect in cases.items():
            r = run_compile(pat)
            assert r.returncode == 0
            assert r.stdout.decode("latin-1") == expect, pat

    def test_canonical_output_is_byte_exact(self):
        """Every catalog pattern must compile to the exact canonical DFA bytes.

        This is the strict byte-level check: it pins lowercase two-digit hex labels,
        ascending range-compressed transitions, the BFS state numbering, dead-state
        pruning, and the header/accept formatting. A merely language-equivalent but
        non-canonical DFA fails here."""
        with open(os.path.join(os.path.dirname(__file__), "compile_truth.json")) as f:
            truth = json.load(f)
        assert len(truth) >= 50, "truth corpus too small"
        for entry in truth:
            pat = entry["pattern"]
            r = run_compile(pat)
            assert r.returncode == 0, (pat, r.stderr)
            got = r.stdout.decode("latin-1")
            assert got == entry["output"], f"non-canonical output for {pat!r}\n--- got ---\n{got}\n--- want ---\n{entry['output']}"

    def test_minimal_canonical_unique(self):
        """Equivalent patterns minimise to byte-identical canonical output."""
        equiv = [
            ("a[bc]", "ab|ac"),
            ("(a|b)*", "(a*b*)*"),
            ("[0-9]", "[[:digit:]]"),
            ("aa", "a{2}"),
            ("colou?r", "color|colour"),
            # compile reports the whole-string automaton, so anchors are dropped:
            ("^abc$", "abc"),
            ("^abc", "abc"),
            ("abc$", "abc"),
            # intersection vs the equivalent subtraction denote the same set:
            ("[a-z&&[^aeiou]]", "[a-z--[aeiou]]"),
            # universal single byte, several spellings:
            ("[^]", "[\\x00-\\xff]"),
            (".|\\n", "[^]"),
            # counted repetition vs explicit alternation/concatenation:
            ("a{2,4}", "aa|aaa|aaaa"),
            ("a{0}bc", "bc"),
            # star of the empty-set language accepts exactly the empty string,
            # same as the empty pattern:
            ("[]*", ""),
            ("[]?", ""),
        ]
        for p, q in equiv:
            rp = run_compile(p)
            rq = run_compile(q)
            assert rp.returncode == 0 and rq.returncode == 0, (p, q)
            assert rp.stdout == rq.stdout, (p, q, rp.stdout, rq.stdout)

    def test_determinism(self):
        """Compiling the same pattern twice yields identical bytes."""
        for pat in ["[a-z--[aeiou]]+", "(ab|cd){2,3}", "0x[[:hexdigit:]]+"]:
            a = run_compile(pat).stdout
            b = run_compile(pat).stdout
            assert a == b, pat

    def test_dead_states_pruned(self):
        """No non-accepting sink reachable to no accept state remains."""
        for pat in PATTERNS:
            r = run_compile(pat)
            if r.returncode != 0:
                continue
            n, accept, trans = parse_dfa(r.stdout.decode("latin-1"))
            if not accept:
                assert n == 1, (pat, n)
                assert trans[0] == {}, (pat, trans[0])
                continue
            reach_accept = set(accept)
            changed = True
            while changed:
                changed = False
                for sid in range(n):
                    if sid in reach_accept:
                        continue
                    for t in trans[sid].values():
                        if t in reach_accept:
                            reach_accept.add(sid)
                            changed = True
                            break
            assert reach_accept == set(range(n)), (pat, reach_accept, n)

    def test_invalid_patterns_rejected(self):
        """Invalid patterns print nothing to stdout and exit nonzero."""
        pat_dir = os.path.join(APP, "data", "patterns")
        for name in sorted(os.listdir(pat_dir)):
            if not name.startswith("bad_"):
                continue
            with open(os.path.join(pat_dir, name), "rb") as fh:
                pat = fh.read().rstrip(b"\n")
            r = subprocess.run([BIN, "compile", pat.decode("latin-1")], capture_output=True)
            assert r.returncode != 0, (name, pat)
            assert r.stdout == b"", (name, pat)

    def test_fixture_patterns_match_reference(self):
        """Shipped pat_*.rsx fixtures all compile and agree with the reference."""
        pat_dir = os.path.join(APP, "data", "patterns")
        strings = sample_strings()
        for name in sorted(os.listdir(pat_dir)):
            if not name.startswith("pat_"):
                continue
            with open(os.path.join(pat_dir, name), "rb") as fh:
                pat = fh.read().rstrip(b"\n")
            r = subprocess.run([BIN, "compile", pat.decode("latin-1")], capture_output=True)
            assert r.returncode == 0, (name, pat, r.stderr)
            dfa = parse_dfa(r.stdout.decode("latin-1"))
            for s in strings:
                exp = refregex.full_match(pat, s)
                got = dfa_accepts(dfa, s)
                assert got == exp, (name, pat, s, exp, got)

    def test_named_set_and_subtraction(self):
        """Class subtraction and named sets denote the exact byte sets."""
        r = run_compile("[a-z--[aeiou]]")
        assert r.returncode == 0
        dfa = parse_dfa(r.stdout.decode("latin-1"))
        consonants = [c for c in range(0x61, 0x7B) if chr(c) not in "aeiou"]
        for c in range(0x61, 0x7B):
            data = bytes([c])
            expect = c in consonants
            assert dfa_accepts(dfa, data) == expect, chr(c)

    def test_counted_bounds(self):
        """Counted repetition accepts exactly the documented copy counts."""
        r = run_compile("a{2,4}")
        assert r.returncode == 0
        dfa = parse_dfa(r.stdout.decode("latin-1"))
        for k in range(0, 7):
            data = b"a" * k
            assert dfa_accepts(dfa, data) == (2 <= k <= 4), k

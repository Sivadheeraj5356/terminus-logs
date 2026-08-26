import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import refscan

APP = "/app"
BIN = os.path.join(APP, "target", "release", "rsx")
PATTERNS_FILE = os.path.join(APP, "data", "patterns.txt")
CORPUS_DIR = os.path.join(APP, "data", "corpus")


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


def run_scan(patterns_path, input_path):
    return subprocess.run(
        [BIN, "scan", "--patterns", patterns_path, "--input", input_path],
        capture_output=True,
    )


def expected_report(patterns_path, input_path):
    patterns = refscan.read_patterns(patterns_path)
    with open(input_path, "rb") as fh:
        data = fh.read()
    out = []
    for p in patterns:
        spans = refscan.scan_pattern(p, data)
        out.append((p, spans))
    return out


def parse_report(stdout_bytes):
    text = stdout_bytes.decode("latin-1")
    assert text.endswith("\n"), "report must end with one trailing newline"
    obj = json.loads(text)
    assert list(obj.keys()) == ["patterns"], "top object has only 'patterns'"
    entries = []
    for e in obj["patterns"]:
        assert list(e.keys()) == ["pattern", "matches"], "entry key order"
        spans = [tuple(x) for x in e["matches"]]
        entries.append((e["pattern"].encode("latin-1"), spans))
    return entries


def corpus_files():
    names = sorted(os.listdir(CORPUS_DIR))
    return [os.path.join(CORPUS_DIR, n) for n in names]


class TestMilestone2:
    def test_binary_exists(self):
        """The release binary builds and is present."""
        assert os.path.exists(BIN)

    def test_milestone1_still_present(self):
        """compile from milestone 1 must still work, since scan reuses it."""
        r = subprocess.run([BIN, "compile", "abc"], capture_output=True)
        assert r.returncode == 0
        assert r.stdout.decode("latin-1") == (
            "states 4\nstart 0\naccept 3\n0: 61=>1\n1: 62=>2\n2: 63=>3\n3:\n"
        )

    def test_scan_main_patterns(self):
        """Scanning the shipped patterns over the edge corpus matches ground truth."""
        for inp in corpus_files():
            r = run_scan(PATTERNS_FILE, inp)
            assert r.returncode == 0, (inp, r.stderr)
            got = parse_report(r.stdout)
            exp = expected_report(PATTERNS_FILE, inp)
            assert [p for p, _ in got] == [p for p, _ in exp], inp
            for (gp, gs), (ep, es) in zip(got, exp):
                assert gs == es, (inp, gp, gs, es)

    def test_entry_order_matches_file(self):
        """Report entries appear in the patterns-file order with raw text."""
        inp = os.path.join(CORPUS_DIR, "edge_overlap.txt")
        r = run_scan(PATTERNS_FILE, inp)
        assert r.returncode == 0
        got = parse_report(r.stdout)
        patterns = refscan.read_patterns(PATTERNS_FILE)
        assert [p for p, _ in got] == patterns

    def test_leftmost_longest(self):
        """foo|foobar takes the longer alternative at each start."""
        pf, inp = self._tmp("foo|foobar\n", "foobarfoofoobar")
        r = run_scan(pf, inp)
        assert r.returncode == 0
        got = parse_report(r.stdout)
        assert got[0][1] == [(0, 6), (6, 9), (9, 15)], got

    def test_nonoverlapping(self):
        """Matches do not overlap; scanning resumes past each match."""
        pf, inp = self._tmp("aa\n", "aaaaa")
        r = run_scan(pf, inp)
        got = parse_report(r.stdout)
        assert got[0][1] == [(0, 2), (2, 4)], got

    def test_anchor_start(self):
        """A leading ^ restricts matches to offset 0."""
        pf, inp = self._tmp("^foo\n", "foo foo foo")
        r = run_scan(pf, inp)
        got = parse_report(r.stdout)
        assert got[0][1] == [(0, 3)], got

    def test_anchor_end(self):
        """A trailing $ restricts matches to the end of the input."""
        pf, inp = self._tmp("foo$\n", "foo foo")
        r = run_scan(pf, inp)
        got = parse_report(r.stdout)
        assert got[0][1] == [(4, 7)], got

    def test_zero_length_progress(self):
        """A pattern that can match empty advances one byte per zero-length hit."""
        pf, inp = self._tmp("a*\n", "baa")
        r = run_scan(pf, inp)
        got = parse_report(r.stdout)
        exp = refscan.scan_pattern(b"a*", b"baa")
        assert got[0][1] == exp, (got, exp)

    def test_class_subtraction_scan(self):
        """Class subtraction works inside the scanner too."""
        pf, inp = self._tmp("[a-z--[aeiou]]+\n", "aeiou bcd xyz")
        r = run_scan(pf, inp)
        got = parse_report(r.stdout)
        exp = refscan.scan_pattern(b"[a-z--[aeiou]]+", b"aeiou bcd xyz")
        assert got[0][1] == exp, (got, exp)

    def test_json_formatting_exact(self):
        """The serialiser emits the exact documented spacing and escaping."""
        pf, inp = self._tmp("[0-9]+\nfoo\n", "ab12 foo")
        r = run_scan(pf, inp)
        assert r.returncode == 0
        text = r.stdout.decode("latin-1")
        expect = (
            '{"patterns": [{"pattern": "[0-9]+", "matches": [[2, 4]]}, '
            '{"pattern": "foo", "matches": [[5, 8]]}]}\n'
        )
        assert text == expect, text

    def test_json_escaping(self):
        """Backslash and quote in a pattern are JSON-escaped in the report."""
        pf, inp = self._tmp('"[^"]*"\n', 'x "ab" y')
        r = run_scan(pf, inp)
        assert r.returncode == 0
        got = parse_report(r.stdout)
        assert got[0][0] == b'"[^"]*"'
        assert got[0][1] == [(2, 6)], got

    def test_parse_error_exit(self):
        """A patterns file with an invalid pattern exits nonzero, empty stdout."""
        pf, inp = self._tmp("[a-\n", "abc")
        r = run_scan(pf, inp)
        assert r.returncode != 0
        assert r.stdout == b""

    def test_mid_pattern_anchor_parse_error(self):
        """An anchor in the middle of a pattern is rejected as a parse error.

        The spec permits ^ only at the very start of a pattern and $ only at
        the very end; a ^ or $ anywhere else is invalid. When such a pattern
        appears in the patterns file the scanner must fail the whole run the
        same way it does for any unparseable pattern: nothing on stdout and a
        nonzero exit status. This exercises the mid-pattern anchor case
        directly rather than leaning on the generic bad-pattern fixtures.
        """
        for bad in ["a^b", "a$b", "ab$cd", "x^y"]:
            pf, inp = self._tmp(bad + "\n", "aXbcd xy")
            r = run_scan(pf, inp)
            assert r.returncode != 0, (bad, r.stdout)
            assert r.stdout == b"", (bad, r.stdout)

    def test_json_escaping_control_byte(self):
        """A raw control byte in a pattern line is escaped as \\u00XX in output.

        The spec escapes every byte < 0x20 in the pattern text as a lowercase
        \\u00XX sequence (and " and \\ as \\" and \\\\), emitting all other bytes
        verbatim. A pattern line containing a literal TAB (0x09) must therefore
        appear in the report's "pattern" field as \\u0009, not as a raw tab and
        not as \\t. This pins the escaping of the pattern text itself.
        """
        pf, inp = self._tmp("\t+\n", "a\t\tb\tc")
        r = run_scan(pf, inp)
        assert r.returncode == 0, r.stderr
        text = r.stdout.decode("latin-1")
        assert '"pattern": "\\u0009+"' in text, text
        assert "\t" not in text, "raw tab must not appear unescaped in the report"
        got = parse_report(r.stdout)
        exp = refscan.scan_pattern(b"\t+", b"a\t\tb\tc")
        assert got[0][1] == exp, (got, exp)

    def test_class_intersection_scan(self):
        """Class intersection && works in the scanner and matches ground truth."""
        pat = "[a-z&&[^aeiou]]+"
        data = "rhythm bcd aeiou xyzzy consonant"
        pf, inp = self._tmp(pat + "\n", data)
        r = run_scan(pf, inp)
        assert r.returncode == 0, r.stderr
        got = parse_report(r.stdout)
        exp = refscan.scan_pattern(pat.encode("latin-1"), data.encode("latin-1"))
        assert got[0][1] == exp, (got, exp)

    def test_anchor_end_longest_and_zero_length(self):
        """`$` selects the longest match ending at input end, plus zero-length.

        For `a*$` over "xxaa" the only nonempty anchored match is the trailing
        run "aa" at (2, 4); then a zero-length match is reported at the very end
        (4, 4). For `[0-9]+$` over multi-line text only the final digit run,
        which actually ends at the input length, is reported -- `$` means the
        end of the whole input, not the end of a line. An off-by-one in the
        resume position, treating `$` as end-of-line, or dropping the terminal
        zero-length hit all diverge here.
        """
        pf, inp = self._tmp("a*$\n", "xxaa")
        got = parse_report(run_scan(pf, inp).stdout)
        assert got[0][1] == [(2, 4), (4, 4)], got
        pf, inp = self._tmp("[0-9]+$\n", "foo123\nbar456\nqux789")
        got = parse_report(run_scan(pf, inp).stdout)
        assert got[0][1] == [(17, 20)], got
        pf, inp = self._tmp("(ab)*\n", "abababXabab")
        got = parse_report(run_scan(pf, inp).stdout)
        exp = refscan.scan_pattern(b"(ab)*", b"abababXabab")
        assert got[0][1] == exp, (got, exp)

    def test_multi_pattern_consistency(self):
        """Several patterns at once match the per-pattern ground truth."""
        pats = "[A-Za-z_][A-Za-z0-9_]*\n[0-9]+\n0x[[:hexdigit:]]+\nba(na)+\n"
        data = "name_1 0xAB 42 banana bananana"
        pf, inp = self._tmp(pats, data)
        r = run_scan(pf, inp)
        assert r.returncode == 0
        got = parse_report(r.stdout)
        exp = expected_report(pf, inp)
        assert [s for _, s in got] == [s for _, s in exp], (got, exp)

    def test_large_corpus_subset(self):
        """A representative slice of the corpus scans correctly for all patterns."""
        names = sorted(os.listdir(CORPUS_DIR))
        chosen = [n for n in names if n.startswith("corpus_")][:30]
        for n in chosen:
            inp = os.path.join(CORPUS_DIR, n)
            r = run_scan(PATTERNS_FILE, inp)
            assert r.returncode == 0, (n, r.stderr)
            got = parse_report(r.stdout)
            exp = expected_report(PATTERNS_FILE, inp)
            for (gp, gs), (ep, es) in zip(got, exp):
                assert gs == es, (n, gp, gs, es)

    def _tmp(self, patterns_text, input_text):
        d = os.path.join("/tmp", "rsx_m2")
        os.makedirs(d, exist_ok=True)
        import hashlib

        h = hashlib.sha1((patterns_text + "||" + input_text).encode("latin-1")).hexdigest()[:12]
        pf = os.path.join(d, "p_" + h + ".txt")
        inf = os.path.join(d, "i_" + h + ".txt")
        with open(pf, "w", encoding="latin-1", newline="") as fh:
            fh.write(patterns_text)
        with open(inf, "w", encoding="latin-1", newline="") as fh:
            fh.write(input_text)
        return pf, inf

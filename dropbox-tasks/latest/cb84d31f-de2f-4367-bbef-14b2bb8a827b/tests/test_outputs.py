"""Verification suite for the gosaw engine.

The game is rods of timber where a turn saws one rod across into two, and whoever makes the last
cut wins. The gaps in the row, the rods of nought units, set the blade for the whole batch: with
an even number of gaps or none the blade is heavy and eats one unit at every cut, so the two
rods left add to one less than the rod sawn and only a rod of three or more can be sawn; with an
odd number of gaps the blade is true and eats nothing, so the two rods add to the rod and a rod
of two saws into two ones. A rod's worth is worked out from the cuts alone under the blade in
force, with no formula, by a small fixed-point sweep, and the same length of rod is in general
worth one thing on a heavy blade and another on a true one. On small batches that sweep, read as
the exclusive-or of the worths of the rods, is required to agree exactly with a full game search
that knows no worth at all, which pins the winning condition, where the worth pulls off the
length, and the way the gaps flip the blade. The tool's output on every batch must match the
sweep, and its reported cut is replayed under the blade the row is set to and required to leave
the opponent a batch of nought worth. Hand cases pin the echo and rod numbering, the gaps, the
out-of-range batches, the skipping of junk lines, the mill-file reading and the exit codes.
"""

import functools
import itertools
import os
import random
import re
import shutil
import subprocess
import tempfile

# The program under test: the compiled engine, run with the mill file as its only argument and
# fed batches on standard input.
APP = ["java", "-cp", "/tmp/sawsplitclasses", "Main"]

# The tool under test is always started through this runner, which drops to an unprivileged
# user first. The verifier's own files are handed to root alone by test.sh, so the tool cannot
# open the reference sweep below and echo its answers back: it has to settle the batch itself.
# Isolating things this way costs a legitimate tool nothing, since it only ever reads the mill
# file it is handed and the batches on its standard input. HOME points at a world-writable place
# so a runtime that wants a home directory has one while running as nobody.
SANDBOX = ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups", "--"]
_ENV = dict(os.environ, HOME="/tmp")

CUT_TERM = re.compile(r"^cut rod (\d+) into (\d+) and (\d+)$")

INT64_MIN = -(2 ** 63)
INT64_MAX = 2 ** 63 - 1


def sandboxed(argv, inp=None, timeout=120.0):
    """Run argv as the unprivileged user and return the completed process."""
    return subprocess.run(SANDBOX + argv, input=inp, capture_output=True,
                          text=True, timeout=timeout, env=_ENV)


def share(path):
    """Widen a fresh temp path just enough for the unprivileged tool to reach it."""
    os.chmod(path, 0o755 if os.path.isdir(path) else 0o644)


def run_bin(longest, positions, timeout=180.0):
    """Feed a batch of positions at a bench with the given rod bound (None for no bound) and
    return the output lines."""
    text = "" if longest is None else "longest: %d\n" % longest
    return _run(text, positions, timeout)


def run_bin_text(text, positions, timeout=180.0):
    """Run with a raw mill-file body (for the file-parsing tests)."""
    return _run(text, positions, timeout)


def _run(text, positions, timeout):
    root = tempfile.mkdtemp(prefix="gosaw-")
    try:
        share(root)
        path = os.path.join(root, "mill.txt")
        with open(path, "w") as fh:
            fh.write(text)
        share(path)
        inp = "\n".join(positions) + "\n"
        p = sandboxed(APP + [path], inp, timeout=timeout)
        assert p.returncode == 0, f"gosaw exited {p.returncode}: {p.stderr[:500]}"
        return p.stdout.split("\n")[:-1] if p.stdout else []
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ----- worth reference -------------------------------------------------------

BOUND = 4096


def _build_dp(add):
    """A rod's worth from the cuts alone under one blade: the smallest whole number that is not
    the worth of any batch the rod can be turned into by one cut. A cut saws a rod into two rods,
    each one or more, whose lengths add to n minus add (add is one on the heavy blade, nought on
    the true blade), and the worth of that pair is the exclusive-or of the two rods' worths. A
    rod too short to saw reaches nothing. No formula is used; the lengths are worked up short
    before long."""
    g = [0] * (BOUND + 1)
    for n in range(1, BOUND + 1):
        reach = set()
        s = n - add
        for a in range(1, s):
            b = s - a
            reach.add(g[a] ^ g[b])
        m = 0
        while m in reach:
            m += 1
        g[n] = m
    return g


_DP_HEAVY = _build_dp(1)
_DP_TRUE = _build_dp(0)


def heavy_blade(rods):
    """The blade is heavy when the number of gaps (rods of nought units) is even or nought, and
    true when it is odd."""
    return sum(1 for r in rods if r == 0) % 2 == 0


def value(n, heavy):
    """The worth of a rod of length n under the blade in force, read straight off the sweep."""
    if n <= 0:
        return 0
    return _DP_HEAVY[n] if heavy else _DP_TRUE[n]


def combined(rods):
    heavy = heavy_blade(rods)
    x = 0
    for r in rods:
        x ^= value(r, heavy)
    return x


def is_int_literal(s):
    if not s:
        return False
    if s[0] == "+" or s[0] == "-":
        s = s[1:]
    return len(s) > 0 and all("0" <= c <= "9" for c in s)


def parse_line(line):
    """Return the parsed rod lengths (a line that produces output), or None for a line that is
    skipped: no fields, a field that is not a whole-number literal, or a field too large to fit
    a signed 64-bit integer."""
    fields = line.split()
    if not fields:
        return None
    rods = []
    for f in fields:
        if not is_int_literal(f):
            return None
        v = int(f)
        if v < INT64_MIN or v > INT64_MAX:
            return None
        rods.append(v)
    return rods


def in_range(rods, longest):
    for r in rods:
        if r < 0 or (longest is not None and r > longest):
            return False
    return True


# ----- full game truth over small batches ------------------------------------


def win_brute(rods):
    """A full game search over a batch of rods with no notion of worth: a batch is a win for the
    player to saw when some cut leaves the opponent a losing batch. The blade is fixed for the
    batch by the parity of the gaps, and no cut ever changes a gap, so the blade never shifts.
    On a heavy blade only a rod of three or more can be sawn, into two rods that add to one less
    than it; on a true blade a rod of two or more can be sawn, into two rods that add to it."""
    heavy = heavy_blade(rods)
    minlen = 3 if heavy else 2
    add = 1 if heavy else 0

    @functools.lru_cache(maxsize=None)
    def wb(t):
        for i in range(len(t)):
            r = t[i]
            if r < minlen:
                continue
            rest = t[:i] + t[i + 1:]
            s = r - add
            for a in range(1, s):
                b = s - a
                nb = rest + (a, b)
                if not wb(tuple(sorted(x for x in nb if x >= minlen))):
                    return True
        return False

    return wb(tuple(sorted(r for r in rods if r >= minlen)))


def brute_verdict(rods):
    return "WIN" if win_brute(rods) else "LOSS"


# ----- output validation -----------------------------------------------------


def check_output_line(line, rods, longest, truth=None):
    """Validate one output line against the worth sweep. For a win, replay the reported cut and
    require it legal and winning under the blade the row is set to: it saws a long-enough rod
    into two rods that each hold at least one unit and add to the rod on a true blade or to one
    less on a heavy blade, and leaves the opponent a batch of nought worth."""
    assert " | " in line, ("no separator", line)
    echo, verdict = line.split(" | ", 1)
    assert echo == " ".join(str(r) for r in rods), ("echo", echo, rods)

    if not in_range(rods, longest):
        assert verdict == "ILLEGAL", ("out of range but not ILLEGAL", line, rods, longest)
        return

    heavy = heavy_blade(rods)
    want = "LOSS" if combined(rods) == 0 else "WIN"
    if truth is not None:
        assert truth == want, ("sweep disagrees with the search", rods, want, truth)

    if verdict == "LOSS":
        assert want == "LOSS", ("said LOSS, sweep says WIN", rods)
        return
    assert verdict.startswith("WIN"), ("bad verdict", verdict, line)
    assert want == "WIN", ("said WIN, sweep says LOSS", rods)
    body = verdict[len("WIN"):]
    assert body.startswith(" "), ("WIN must be followed by a cut", verdict)
    move = body[1:]

    cm = CUT_TERM.match(move)
    assert cm, ("bad cut", move, line)
    i = int(cm.group(1))
    a = int(cm.group(2))
    b = int(cm.group(3))
    assert 1 <= i <= len(rods), ("rod index out of range", i, line)
    idx = i - 1
    assert a >= 1 and b >= 1, ("a cut must leave two rods of at least one unit", move)
    minlen = 3 if heavy else 2
    assert rods[idx] >= minlen, ("rod too short to saw under this blade", move, rods, heavy)
    want_sum = rods[idx] - 1 if heavy else rods[idx]
    assert a + b == want_sum, ("the two rods add up wrong for this blade", move, rods, heavy)
    new = rods[:idx] + [a, b] + rods[idx + 1:]
    assert combined(new) == 0, ("cut does not leave a loss", rods, new)


def produced_lines(positions):
    return [p for p in positions if parse_line(p) is not None]


def check_batch(longest, positions, brute=False):
    """Run a batch of positions, and validate every output line against the sweep. When brute
    is set, each in-range position is also cross-checked against a full game search. Returns the
    tool's output lines."""
    got = run_bin(longest, positions)
    produced = produced_lines(positions)
    assert len(got) == len(produced), ("line count", len(got), len(produced), positions[:20])
    for line, pos in zip(got, produced):
        rods = parse_line(pos)
        truth = brute_verdict(rods) if (brute and in_range(rods, longest)) else None
        check_output_line(line, rods, longest, truth=truth)
    return got


# ----- the worth sweep against the full game search --------------------------


def test_sweep_reading_matches_the_search():
    """The exclusive-or reading off the worth sweep, taken over the rods of a batch under the
    blade the gaps set, must agree with a full game search that knows no worth at all, on every
    batch of up to four rods of at most nine units. This pins that the game decomposes the way
    the worth reading claims, where the worth pulls off the length, and the way the gaps flip the
    blade."""
    for n in range(0, 5):
        for combo in itertools.product(range(0, 10), repeat=n):
            rods = list(combo)
            want = "LOSS" if combined(rods) == 0 else "WIN"
            assert brute_verdict(rods) == want, (rods, want, brute_verdict(rods))


# ----- the tool against the sweep on small batches ---------------------------


def test_tool_matches_sweep_on_small_batches():
    """Every batch of up to four rods of at most seven units, fed through and each verdict and
    cut checked against the sweep. A build that scores plain nim on the rod lengths gets these
    wrong and fails here, as does one that reads the same blade for every batch."""
    positions = []
    for n in range(0, 5):
        for combo in itertools.product(range(0, 8), repeat=n):
            positions.append(" ".join(str(x) for x in combo))
    check_batch(None, positions)


def test_tool_matches_search_position_by_position():
    """Every batch of up to three rods of at most eight units, cross-checked against a full game
    search. This pins the per-rod worth, the winning rule and the gap-set blade. A plain-nim
    build, one that forgets the heavy blade eats a unit, or one that ignores the gaps lands these
    backwards."""
    positions = []
    for n in range(0, 4):
        for combo in itertools.product(range(0, 9), repeat=n):
            positions.append(" ".join(str(x) for x in combo))
    check_batch(None, positions, brute=True)


# ----- the decisive small positions ------------------------------------------


def test_two_units_is_a_second_player_win():
    """A single rod of two units. There are no gaps, so the blade is heavy and eats the middle
    unit, and two units cannot fall into two rods of one: there is no cut to make and the player
    to saw has already lost. A plain-nim reading on the length, or a reader who saws it into a
    one and a one forgetting the heavy blade, calls it a win."""
    got = run_bin(None, ["2"])
    assert got == ["2 | LOSS"], got
    assert brute_verdict([2]) == "LOSS"
    check_output_line(got[0], [2], None, truth="LOSS")


def test_one_gap_turns_the_two_into_a_win():
    """The same rod of two units set beside a single gap. One gap is an odd count, so the blade
    runs true and eats nothing, and now the two saws cleanly into a one and a one: the player to
    saw wins by making that cut. A reader who fixes one blade for every batch, or ignores the
    gaps, keeps calling the two a loss and fails here. The gap flips the outcome."""
    got = run_bin(None, ["0 2"])
    assert len(got) == 1, got
    assert got[0].startswith("0 2 | WIN "), got
    assert brute_verdict([0, 2]) == "WIN"
    check_output_line(got[0], [0, 2], None, truth="WIN")


def test_gap_parity_flips_the_same_row():
    """One rod of six units under a changing count of gaps. With no gap and with two gaps the
    blade is heavy and the six is a loss; with one gap and with three gaps the blade is true and
    the six is a win. The verdict on the six turns on the parity of the gaps sharing its row, not
    on the six alone."""
    got = run_bin(None, ["6", "0 6", "0 0 6", "0 0 0 6"])
    assert got[0] == "6 | LOSS", got
    assert got[1].startswith("0 6 | WIN "), got
    assert got[2] == "0 0 6 | LOSS", got
    assert got[3].startswith("0 0 0 6 | WIN "), got
    check_batch(None, ["6", "0 6", "0 0 6", "0 0 0 6"], brute=True)


def test_same_rods_under_every_gap_parity():
    """The same nonzero rods carried under nought, one, two and three gaps, so the blade swings
    heavy, true, heavy, true across otherwise identical rows. Every verdict and cut is
    cross-checked against a full game search, pinning that the whole batch turns on the parity of
    the gaps and nothing else. A build that reads a single blade lands half of these backwards."""
    sets = [["3", "5"], ["5", "8"], ["6", "6"], ["4", "7"], ["3", "4", "7"]]
    positions = []
    for base in sets:
        for gaps in range(0, 4):
            positions.append(" ".join(["0"] * gaps + base))
    check_batch(None, positions, brute=True)


def test_true_blade_hand_values():
    """Hand rows on the true blade, one gap so the blade eats nothing. On the true blade a rod is
    a loss on its own exactly when its length is odd or nought, so a lone even rod beside a gap
    is a win and a lone odd rod beside a gap is a loss. Pinned against the search."""
    got = run_bin(None, ["0 3", "0 4", "0 5", "0 7", "0 8"])
    assert got[0] == "0 3 | LOSS", got
    assert got[1].startswith("0 4 | WIN "), got
    assert got[2] == "0 5 | LOSS", got
    assert got[3] == "0 7 | LOSS", got
    assert got[4].startswith("0 8 | WIN "), got
    check_batch(None, ["0 3", "0 4", "0 5", "0 7", "0 8"], brute=True)


def test_six_units_is_a_second_player_win():
    """A single rod of six units is a loss for the player to saw on the heavy blade though its
    length is not nought: every cut of it leaves a batch the opponent wins. A plain-nim reading
    calls it a win off the length."""
    got = run_bin(None, ["6"])
    assert got == ["6 | LOSS"], got
    check_output_line(got[0], [6], None, truth="LOSS")


def test_naive_reading_lands_backwards():
    """Batches a plain-nim reading on the rod lengths gets backwards, each pinned by the full
    game search. A build that scores a rod by the units standing in it fails these."""
    check_batch(None, ["2", "6", "1", "10", "3 4 7", "1 6 7", "2 3", "5 6"], brute=True)


def test_forgetting_the_kerf_lands_backwards():
    """Batches a reader gets backwards by forgetting the heavy blade eats a unit, sawing a rod
    into parts that add to its length rather than one less, each pinned by the search. A build
    that drops the wasted unit shifts the whole worth table and fails these."""
    check_batch(None, ["2", "3", "5", "6", "7", "9", "2 5", "3 7", "4 6 6"], brute=True)


def test_ignoring_the_gaps_lands_backwards():
    """Batches with an odd number of gaps, where the blade runs true, that a reader gets
    backwards by fixing one heavy blade for every batch, each pinned by the search. A build that
    reads the worth of every rod off the heavy table, whatever the gaps, fails these."""
    check_batch(None, ["0 2", "0 6", "0 4", "3 0 4", "0 2 5", "0 0 0 6", "2 0 2", "0 3 5",
                        "0 8 8", "0 7 4"], brute=True)


def test_worths_are_not_the_length():
    """Pairs and triples on and around the lengths whose worth has come off the length, each
    pinned by the search. A build that keeps every rod at its length lands these backwards."""
    check_batch(None, ["3 5", "5 6", "3 4 7", "6 10 12", "4 7", "7 8", "3 7 4",
                       "2 6", "6 6", "5 8"], brute=True)


# ----- larger winning positions past any search ------------------------------


def test_larger_winning_positions():
    """Larger winning batches well past any game search, labelled by the worth sweep under the
    blade the gaps set. Every reported cut is replayed to confirm it lands a loss, so a build
    that mislocates the worth, reads the wrong blade or botches the cut on longer rods fails."""
    cases = ["259 4 3", "1027 3 4", "512 513", "515 516", "1023 1025",
             "1000 2000 5", "700 701 3", "2047 3 4", "6 10 12", "18 20 25",
             "0 1000 1001", "0 0 0 777 778", "0 2046 2047", "0 0 511 512",
             "0 1023 2047 4"]
    for case in cases:
        got = run_bin(None, [case])
        assert len(got) == 1, got
        rods = [int(x) for x in case.split()]
        assert combined(rods) != 0, (case, "should be a first-player win")
        check_output_line(got[0], rods, None, truth="WIN")


# ----- gaps ------------------------------------------------------------------


def test_gaps_hold_their_place_and_are_numbered():
    """Rods of nought units are counted in the numbering and any reported cut names the right
    rod. The echo keeps the gaps, and the verdicts are validated against the sweep under the
    blade the gap count sets for each row."""
    check_batch(None, ["0 3 0", "3 0 4", "0 5 0 6", "0 0 7", "4 0 0 5", "0 6 0", "0 0 0 5"])


# ----- out-of-range positions ------------------------------------------------


def test_over_the_bound_is_illegal():
    """A rod above the bench bound puts the batch out of range: it is echoed and reported
    ILLEGAL with no verdict. Rods at or under the bound play normally."""
    got = run_bin(10, ["11", "10", "0 11", "5 20", "10 10", "3 4 5"])
    assert got[0] == "11 | ILLEGAL", got
    assert got[1] != "10 | ILLEGAL", got
    assert got[2] == "0 11 | ILLEGAL", got
    assert got[3] == "5 20 | ILLEGAL", got
    assert got[4] != "10 10 | ILLEGAL", got
    assert got[5] != "3 4 5 | ILLEGAL", got
    check_batch(10, ["11", "10", "0 11", "5 20", "10 10", "3 4 5"])


def test_negative_is_out_of_range_not_skipped():
    """A negative field is a whole number all the same: it is read, judged out of range, and the
    batch is echoed and reported ILLEGAL. It is never treated as junk and never dropped on that
    account."""
    got = run_bin(None, ["-1", "-1 2", "3 -5 4", "0 -1"])
    assert got == ["-1 | ILLEGAL", "-1 2 | ILLEGAL", "3 -5 4 | ILLEGAL", "0 -1 | ILLEGAL"], got


def test_number_out_of_range_versus_not_a_number():
    """-1 is a number out of range and is reported; x is not a number and the line is dropped.
    Fed together, only the -1 line and the 3 5 line come back."""
    got = run_bin(None, ["-1", "x", "1 y", "3 5"])
    assert len(got) == 2, got
    assert got[0] == "-1 | ILLEGAL", got
    assert got[1].startswith("3 5 | WIN "), got
    check_output_line(got[1], [3, 5], None)


def test_non_numeric_and_blank_lines_skipped():
    """Blank lines and lines carrying a field that is not a whole-number literal are dropped with
    no output. A decimal point, an underscore, a hex marker and a letter are all not
    whole-number literals."""
    got = run_bin(None, ["", "   ", "3 x 5", "1 2 3.0", "1_000", "0x4", "3 4 7"])
    assert len(got) == 1, got
    assert got[0].startswith("3 4 7 | "), got
    check_output_line(got[0], [3, 4, 7], None)


def test_oversized_literals_are_skipped():
    """A run of digits too large to fit a signed 64-bit integer is not a whole-number literal, so
    a line carrying one is skipped with no output, the same as any other non-literal field. A
    signed oversized field is skipped too, never reported out of range."""
    big = "9" * 25
    got = run_bin(None, [big, "-" + big, big + " 2", "3 4 7"])
    assert len(got) == 1, got
    assert got[0].startswith("3 4 7 | "), got
    check_output_line(got[0], [3, 4, 7], None)


def test_int64_boundary_literals():
    """The boundary of a signed 64-bit integer. The largest and smallest values that fit are
    whole-number literals and are read, then judged out of range under this bench; a value one
    past either end does not fit, so its line is skipped. The played 3 5 that follows comes
    back."""
    got = run_bin(100, ["9223372036854775807", "9223372036854775808",
                        "-9223372036854775808", "-9223372036854775809", "3 5"])
    assert got[0] == "9223372036854775807 | ILLEGAL", got
    assert got[1] == "-9223372036854775808 | ILLEGAL", got
    assert got[2].startswith("3 5 | WIN "), got
    check_output_line(got[2], [3, 5], 100)


# ----- echo ------------------------------------------------------------------


def test_malformed_signs_and_signed_zero():
    """A whole-number literal carries at most one leading sign. A doubled or crossed sign is not
    a literal, so the line is skipped. A signed zero is the number nought and plays: a lone gap
    is a loss."""
    got = run_bin(None, ["++1", "--1", "+-1", "1 +-2", "-0", "+0"])
    assert got == ["0 | LOSS", "0 | LOSS"], got


def test_echo_normalizes_spacing_and_signs():
    got = run_bin(None, ["  3    4  5 ", "007 0", "+3 5"])
    assert got[0].startswith("3 4 5 | "), got
    assert got[1].startswith("7 0 | "), got
    assert got[2].startswith("3 5 | "), got
    check_batch(None, ["  3    4  5 ", "007 0", "+3 5"])


# ----- mill-file parsing -----------------------------------------------------


def test_default_is_no_bound():
    got = run_bin_text("# a note, nothing set\n", ["1000 2000"])
    assert got[0] != "1000 2000 | ILLEGAL", got
    check_output_line(got[0], [1000, 2000], None)


def test_last_bound_value_wins():
    got = run_bin_text("longest: 5\nlongest: 100\n", ["50"])
    assert len(got) == 1 and got[0].startswith("50 | "), got
    check_output_line(got[0], [50], 100)
    got = run_bin_text("longest: 100\nlongest: 5\n", ["50"])
    assert got == ["50 | ILLEGAL"], got


def test_bound_ignores_non_digit_and_signed_words():
    got = run_bin_text("longest: five\n", ["500"])
    assert got[0] != "500 | ILLEGAL", got
    got = run_bin_text("longest: -3\n", ["500"])
    assert got[0] != "500 | ILLEGAL", got
    got = run_bin_text("longest: +5\n", ["500"])
    assert got[0] != "500 | ILLEGAL", got
    got = run_bin_text("longest: 5 units please\n", ["3", "6"])
    assert got == ["3 | WIN cut rod 1 into 1 and 1", "6 | ILLEGAL"], got


def test_comment_stripped_from_bound_line():
    got = run_bin_text("longest: 5   # small bench\n", ["3", "6"])
    assert got == ["3 | WIN cut rod 1 into 1 and 1", "6 | ILLEGAL"], got


def test_bound_zero_allows_only_gaps():
    got = run_bin_text("longest: 0\n", ["0", "0 0", "1", "0 1"])
    assert got == ["0 | LOSS", "0 0 | LOSS", "1 | ILLEGAL", "0 1 | ILLEGAL"], got


# ----- exit codes ------------------------------------------------------------


def test_missing_argument_exits_two():
    """Running with no mill path writes nothing and exits two."""
    p = sandboxed(APP, "3\n", timeout=30.0)
    assert p.returncode == 2, f"expected exit 2, got {p.returncode}"
    assert p.stdout == "", repr(p.stdout)


def test_extra_argument_exits_two():
    """Running with more than one argument writes nothing and exits two."""
    p = sandboxed(APP + ["a", "b"], "3\n", timeout=30.0)
    assert p.returncode == 2, f"expected exit 2, got {p.returncode}"
    assert p.stdout == "", repr(p.stdout)


def test_unreadable_mill_file_exits_two():
    """A mill path that cannot be read writes nothing and exits two."""
    p = sandboxed(APP + ["/no/such/mill/file"], "3\n", timeout=30.0)
    assert p.returncode == 2, f"expected exit 2, got {p.returncode}"
    assert p.stdout == "", repr(p.stdout)


def test_mill_path_that_is_a_directory_exits_two():
    """A mill path that names a directory writes nothing and exits two."""
    d = tempfile.mkdtemp(prefix="gosaw-")
    try:
        share(d)
        p = sandboxed(APP + [d], "3\n", timeout=30.0)
        assert p.returncode == 2, f"expected exit 2, got {p.returncode}"
        assert p.stdout == "", repr(p.stdout)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_good_run_exits_zero():
    """A run over a readable mill file and a batch exits zero with its one line."""
    root = tempfile.mkdtemp(prefix="gosaw-")
    try:
        share(root)
        path = os.path.join(root, "mill.txt")
        with open(path, "w") as fh:
            fh.write("longest: 10\n")
        share(path)
        p = sandboxed(APP + [path], "3 4 7\n", timeout=30.0)
        assert p.returncode == 0, f"expected exit 0, got {p.returncode}"
        lines = p.stdout.split("\n")
        assert len(lines) == 2 and lines[1] == "", repr(p.stdout)
        assert lines[0].startswith("3 4 7 | WIN "), repr(p.stdout)
        check_output_line(lines[0], [3, 4, 7], None)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ----- random differentials --------------------------------------------------


def rand_small(rng):
    n = rng.randint(0, 5)
    rods = [rng.choice([0, 0, 1, 1, 2, 2, 3, 4, 5, 6, 6, 7, 7, 8]) for _ in range(n)]
    return " ".join(str(r) for r in rods)


def test_random_small_batches_match_the_sweep():
    """Random small batches, weighted so a fair share carry gaps, every verdict and cut checked
    against the sweep. A plain-nim build, one that forgets the heavy blade, or one that ignores
    the gaps fails."""
    rng = random.Random(80531)
    positions = [rand_small(rng) for _ in range(500)]
    check_batch(None, positions)


def test_random_small_batches_match_the_search():
    """The same shape of random small batches cross-checked against the full game search to pin
    the per-rod worth and the gap-set blade."""
    rng = random.Random(6021)
    positions = [rand_small(rng) for _ in range(300)]
    check_batch(None, positions, brute=True)


def rand_wide(rng):
    n = rng.randint(1, 9)
    vmax = rng.choice([15, 31, 63, 127, 255, 511, 1023, 2047])
    rods = [rng.randint(0, vmax) for _ in range(n)]
    # fold in extra gaps on some batches so both blades are exercised at width
    for _ in range(rng.randint(0, 2)):
        rods.append(0)
    rng.shuffle(rods)
    return " ".join(str(r) for r in rods)


def test_random_wide_batches_match_the_sweep():
    """Wider batches past any game search, a mix of gap parities so both blades run: the sweep
    labels them and every reported winning cut is replayed and checked."""
    rng = random.Random(20719)
    positions = [rand_wide(rng) for _ in range(500)]
    check_batch(None, positions)


def test_random_near_swapped_sizes():
    """Batches of small rods, gaps included, clustered on and around the lengths whose worth has
    come off the length, checked against the sweep where the worth and the blade are easiest to
    get backwards."""
    rng = random.Random(4095)
    positions = []
    for _ in range(400):
        n = rng.randint(1, 4)
        positions.append(" ".join(str(rng.choice([0, 0, 1, 2, 3, 4, 5, 6, 7, 8])) for _ in range(n)))
    check_batch(None, positions)


def test_random_with_a_bound_mixes_illegal():
    """Random batches at a bench with a bound, so a mix of legal and out-of-range batches come
    together, gaps among them: the line count and the ILLEGAL reports are pinned alongside the
    verdicts."""
    rng = random.Random(272727)
    positions = []
    for _ in range(300):
        n = rng.randint(1, 5)
        positions.append(" ".join(str(rng.choice([0, 0] + list(range(0, 561)))) for _ in range(n)))
    check_batch(512, positions)

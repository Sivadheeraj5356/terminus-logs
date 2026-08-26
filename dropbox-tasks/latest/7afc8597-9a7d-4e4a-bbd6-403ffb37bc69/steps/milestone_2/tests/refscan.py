"""Independent ground-truth scanner built on the reference matcher.

Computes leftmost-longest, non-overlapping match spans directly from the
backtracking matcher, deliberately not the DFA-based approach of the program
under test.
"""

import refregex


def longest_at(node, astart, aend, data, start):
    if astart and start != 0:
        return None
    best = None
    for end in refregex.match_set(node, data, start):
        if aend and end != len(data):
            continue
        if best is None or end > best:
            best = end
    return best


def scan_pattern(pattern_bytes, data):
    node = refregex.parse(pattern_bytes)
    astart, aend, core = refregex.strip_anchors(node)
    spans = []
    start = 0
    n = len(data)
    while start <= n:
        end = longest_at(core, astart, aend, data, start)
        if end is None:
            start += 1
            continue
        spans.append((start, end))
        if end > start:
            start = end
        else:
            start += 1
    return spans


def read_patterns(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    out = []
    for line in raw.split(b"\n"):
        line = line.replace(b"\r", b"")
        if line == b"":
            continue
        out.append(line)
    return out

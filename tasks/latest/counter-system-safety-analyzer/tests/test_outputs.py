"""Verifier for the counter-system cover analyzer.

Self-contained: it restores the read-only sources, checks the editable
analysis file for banned imports/identifiers and stray Go files, builds the
agent's code offline, and then runs an all-or-nothing battery. Each battery
case is a counter system plus cover queries; the agent's binary must return
exactly the query verdicts of an embedded reference analyzer, which was
cross-validated against exact state enumeration on bounded systems.
"""
import json
import os
import random
import re
import shutil
import subprocess

APP = os.environ.get("CC_APP", "/app")
PINNED = os.environ.get("CC_PINNED", "/tests/pinned")

# The instruction allows the full Go standard library plus coverd/model, and
# forbids only capability packages (process execution, filesystem, networking,
# environment access, reflection, unsafe, cgo). Enforce exactly that: any
# import is permitted unless its path is, or lives under, a forbidden root.
FORBIDDEN_IMPORT_ROOTS = {
    "os", "net", "syscall", "unsafe", "reflect", "plugin", "runtime",
    "io/ioutil", "C",
}
ALLOWED_GO_FILES = {
    "main.go",
    "model/model.go",
    "analysis/analysis.go",
}

VAL_MAX = 1000
OMEGA = -1  # internal unbounded marker; never appears in I/O


# --------------------------------------------------------------------------
# reference analyzer (correct behaviour only)
# --------------------------------------------------------------------------
class _Malformed(Exception):
    pass


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _vec(obj, n, key):
    v = obj.get(key)
    if not isinstance(v, list) or len(v) != n:
        raise _Malformed()
    for x in v:
        if not _is_int(x) or x < 0 or x > VAL_MAX:
            raise _Malformed()
    return list(v)


def _geq(a, b):
    """a >= b componentwise, OMEGA in a exceeding everything."""
    for x, y in zip(a, b):
        if x != OMEGA and (y == OMEGA or x < y):
            return False
    return True


def _enabled(m, take):
    for x, t in zip(m, take):
        if x != OMEGA and x < t:
            return False
    return True


def _fire(m, take, give):
    out = []
    for x, t, g in zip(m, take, give):
        out.append(OMEGA if x == OMEGA else x - t + g)
    return out


def _accelerate(m, path):
    """Classic ancestor acceleration: any coordinate strictly above some
    dominated ancestor on the current path becomes unbounded."""
    out = list(m)
    for anc in path:
        lanc = list(anc)
        if _geq(out, lanc) and out != lanc:
            for i in range(len(out)):
                if lanc[i] != OMEGA and out[i] != OMEGA and out[i] > lanc[i]:
                    out[i] = OMEGA
    return out


def km_markings(n, rules, start, budget=200000):
    """Classic coverability tree: returns every tree marking (with OMEGA
    coordinates). A branch stops when its marking repeats an ancestor on its
    own path; no cross-branch pruning is applied.

    Raises RuntimeError when the node budget is exhausted (used only to
    filter generated battery candidates; hand and shipped cases stay far
    below it).
    """
    all_markings = []
    stack = [(tuple(start), ())]
    nodes = 0
    while stack:
        m, path = stack.pop()
        all_markings.append(list(m))
        nodes += 1
        if nodes > budget:
            raise RuntimeError("budget")
        newpath = path + (m,)
        for take, give in rules:
            if not _enabled(m, take):
                continue
            child = _fire(m, take, give)
            child = _accelerate(child, newpath)
            tchild = tuple(child)
            if tchild in newpath:
                all_markings.append(child)
                continue
            stack.append((tchild, newpath))
    return all_markings


def ref_answers(job):
    n = job["counters"]
    rules = [(r["take"], r["give"]) for r in job["rules"]]
    marks = km_markings(n, rules, job["start"])
    out = []
    for q in job["queries"]:
        out.append(any(_geq(m, q) for m in marks))
    return out


def ref_run(job):
    try:
        if not isinstance(job, dict):
            raise _Malformed()
        n = job.get("counters")
        if not _is_int(n) or n < 1 or n > 12:
            raise _Malformed()
        rules = job.get("rules")
        if not isinstance(rules, list) or len(rules) > 16:
            raise _Malformed()
        norm_rules = []
        for r in rules:
            if not isinstance(r, dict):
                raise _Malformed()
            norm_rules.append({"take": _vec(r, n, "take"),
                               "give": _vec(r, n, "give")})
        start = _vec(job, n, "start")
        queries = job.get("queries")
        if not isinstance(queries, list) or len(queries) > 32:
            raise _Malformed()
        norm_q = []
        for q in queries:
            if not isinstance(q, list) or len(q) != n:
                raise _Malformed()
            for x in q:
                if not _is_int(x) or x < 0 or x > VAL_MAX:
                    raise _Malformed()
            norm_q.append(list(q))
        clean = {"counters": n, "rules": norm_rules, "start": start,
                 "queries": norm_q}
        return {"covered": ref_answers(clean)}
    except _Malformed:
        return {"malformed": True}


# --------------------------------------------------------------------------
# battery: hand cases + seeded random systems
# --------------------------------------------------------------------------
def _rule(take, give):
    return {"take": take, "give": give}


def hand_cases():
    """Counter systems chosen to pin every semantic corner."""
    cases = []

    # trivial: no rules, query against the start itself
    cases.append({"counters": 2, "rules": [], "start": [1, 0],
                  "queries": [[1, 0], [0, 1], [2, 0], [0, 0]]})
    # a simple producer: one counter grows without bound
    cases.append({"counters": 2, "rules": [_rule([1, 0], [1, 1])],
                  "start": [1, 0],
                  "queries": [[1, 5], [0, 100], [2, 0], [1, 1000]]})
    # growth requires a chain of two rules (parent-only acceleration misses it)
    cases.append({"counters": 3,
                  "rules": [_rule([1, 0, 0], [0, 1, 0]),
                            _rule([0, 1, 0], [1, 0, 1])],
                  "start": [1, 0, 0],
                  "queries": [[0, 0, 50], [1, 0, 3], [0, 1, 3], [1, 1, 0]]})
    # bounded loop: tokens circulate, never grow
    cases.append({"counters": 2,
                  "rules": [_rule([1, 0], [0, 1]), _rule([0, 1], [1, 0])],
                  "start": [2, 0],
                  "queries": [[2, 0], [0, 2], [1, 1], [2, 1], [3, 0]]})
    # consuming a bounded resource gates the producer
    cases.append({"counters": 3,
                  "rules": [_rule([1, 1, 0], [1, 0, 1])],
                  "start": [1, 3, 0],
                  "queries": [[0, 0, 3], [0, 0, 4], [1, 3, 0], [1, 0, 3]]})
    # unbounded feeder unlocks a second stage arbitrarily often
    cases.append({"counters": 4,
                  "rules": [_rule([1, 0, 0, 0], [1, 1, 0, 0]),
                            _rule([0, 1, 0, 0], [0, 0, 1, 0]),
                            _rule([0, 0, 2, 0], [0, 0, 0, 1])],
                  "start": [1, 0, 0, 0],
                  "queries": [[0, 0, 0, 7], [0, 3, 3, 3], [1, 0, 0, 1],
                              [0, 0, 0, 1000]]})
    # mutual exclusion: both criticals at once must stay uncoverable
    cases.append({"counters": 3,
                  "rules": [_rule([1, 1, 0], [0, 1, 1]),
                            _rule([0, 1, 1], [1, 1, 0])],
                  "start": [2, 1, 0],
                  "queries": [[0, 1, 2], [1, 1, 1], [0, 0, 2], [2, 1, 1]]})
    # weight-2 arcs: parity matters
    cases.append({"counters": 2,
                  "rules": [_rule([2, 0], [0, 1])],
                  "start": [5, 0],
                  "queries": [[0, 2], [1, 2], [0, 3], [5, 0]]})
    # a rule that is never enabled
    cases.append({"counters": 2,
                  "rules": [_rule([3, 0], [0, 9])],
                  "start": [2, 0],
                  "queries": [[0, 1], [2, 0]]})
    # growth only after a one-way mode switch spends the seed token
    cases.append({"counters": 3,
                  "rules": [_rule([1, 0, 0], [0, 1, 0]),
                            _rule([0, 1, 0], [0, 1, 1])],
                  "start": [1, 0, 0],
                  "queries": [[0, 1, 9], [1, 0, 1], [0, 0, 30], [1, 1, 0]]})
    # two independent unbounded counters, never simultaneously above a joint
    cases.append({"counters": 3,
                  "rules": [_rule([1, 0, 0], [0, 1, 0]),
                            _rule([1, 0, 0], [0, 0, 1]),
                            _rule([0, 1, 0], [0, 2, 0])],
                  "start": [1, 0, 0],
                  "queries": [[0, 8, 0], [0, 0, 1], [0, 8, 1], [0, 1, 1]]})

    # malformed shapes
    cases.append({"counters": 0, "rules": [], "start": [], "queries": []})
    cases.append({"counters": 2, "rules": [], "start": [1], "queries": []})
    cases.append({"counters": 2, "rules": [_rule([1], [0, 0])],
                  "start": [1, 0], "queries": []})
    cases.append({"counters": 2, "rules": [], "start": [1, -1], "queries": []})
    cases.append({"counters": 2, "rules": [], "start": [1, 0],
                  "queries": [[1, 0, 0]]})
    cases.append({"counters": 2, "rules": [], "start": [1, 0],
                  "queries": [[1, 1001]]})
    cases.append({"counters": 2, "rules": [{"take": [1, 0]}],
                  "start": [1, 0], "queries": []})
    cases.append({"counters": 2, "rules": [], "start": [1, True],
                  "queries": []})
    cases.append({"counters": "2", "rules": [], "start": [1, 0],
                  "queries": []})
    cases.append({"counters": 2, "rules": {}, "start": [1, 0], "queries": []})
    # malformed by exceeding the declared size bounds
    cases.append({"counters": 13, "rules": [], "start": [0] * 13, "queries": []})
    cases.append({"counters": 2,
                  "rules": [_rule([0, 0], [0, 0]) for _ in range(17)],
                  "start": [0, 0], "queries": []})
    cases.append({"counters": 2, "rules": [], "start": [0, 0],
                  "queries": [[0, 0] for _ in range(33)]})
    return cases


# Adversarial systems on which approximate exploration strategies (unsound
# saturation, cross-branch subsumption, bounded search) return wrong verdicts.
TRAP_SYSTEMS = [
    {"counters": 4, "rules": [{"take": [0, 0, 2, 1], "give": [1, 0, 0, 0]}, {"take": [0, 2, 0, 0], "give": [1, 0, 0, 1]}, {"take": [0, 0, 0, 0], "give": [0, 2, 0, 1]}], "start": [0, 2, 2, 0], "queries": [[4, 4, 2, 2], [0, 3, 4, 0], [1, 4, 2, 1], [4, 0, 4, 3], [0, 2, 2, 0], [0, 2, 2, 1]]},
    {"counters": 5, "rules": [{"take": [2, 1, 0, 1, 0], "give": [2, 0, 2, 1, 1]}, {"take": [2, 2, 0, 1, 0], "give": [0, 1, 2, 0, 1]}, {"take": [0, 2, 2, 0, 0], "give": [0, 0, 1, 1, 0]}, {"take": [0, 0, 0, 0, 2], "give": [0, 0, 0, 0, 0]}, {"take": [0, 0, 0, 0, 0], "give": [0, 0, 1, 0, 2]}], "start": [2, 1, 0, 1, 0], "queries": [[3, 3, 1, 3, 4], [2, 0, 2, 1, 1], [2, 0, 2, 1, 1], [2, 20, 2, 2, 2], [2, 2, 2, 2, 700]]},
    {"counters": 5, "rules": [{"take": [0, 0, 2, 0, 0], "give": [2, 0, 0, 1, 0]}, {"take": [1, 0, 2, 0, 2], "give": [2, 2, 2, 1, 1]}, {"take": [0, 0, 0, 0, 0], "give": [1, 1, 0, 0, 0]}, {"take": [1, 0, 0, 0, 1], "give": [0, 2, 1, 2, 0]}, {"take": [0, 2, 0, 1, 2], "give": [0, 0, 0, 0, 2]}], "start": [1, 2, 2, 2, 2], "queries": [[3, 4, 0, 7, 0], [2, 2, 1, 3, 3], [700, 0, 1, 2, 0], [1, 6, 2, 7, 0]]},
    {"counters": 4, "rules": [{"take": [0, 2, 2, 0], "give": [1, 0, 2, 0]}, {"take": [0, 0, 0, 0], "give": [2, 0, 0, 0]}, {"take": [0, 0, 0, 2], "give": [1, 0, 2, 1]}, {"take": [0, 1, 0, 2], "give": [0, 0, 0, 0]}], "start": [1, 2, 2, 1], "queries": [[1, 2, 2, 1], [2, 1, 2, 1], [2, 700, 1, 2], [2, 0, 2, 100], [1, 1, 0, 2], [1, 700, 1, 0], [0, 1, 2, 4]]},
    {"counters": 2, "rules": [{"take": [2, 0], "give": [1, 1]}, {"take": [2, 1], "give": [0, 0]}, {"take": [0, 0], "give": [0, 2]}], "start": [2, 0], "queries": [[2, 0], [0, 100], [1, 2], [2, 0], [2, 0], [3, 1], [3, 3], [3, 4]]},
    {"counters": 5, "rules": [{"take": [0, 0, 2, 0, 1], "give": [0, 0, 2, 0, 2]}, {"take": [0, 0, 1, 0, 1], "give": [0, 0, 0, 0, 1]}, {"take": [0, 0, 0, 1, 2], "give": [0, 0, 1, 0, 2]}, {"take": [2, 0, 1, 1, 0], "give": [0, 1, 2, 0, 0]}, {"take": [0, 0, 0, 0, 0], "give": [0, 1, 1, 0, 0]}], "start": [2, 2, 0, 1, 2], "queries": [[0, 0, 1, 2, 1], [2, 2, 0, 1, 700], [2, 2, 0, 1, 2], [0, 2, 20, 1, 1]]},
    {"counters": 5, "rules": [{"take": [0, 2, 1, 0, 0], "give": [0, 0, 1, 0, 0]}, {"take": [2, 2, 0, 0, 0], "give": [1, 0, 0, 0, 2]}, {"take": [2, 0, 1, 2, 0], "give": [0, 2, 0, 0, 0]}, {"take": [0, 1, 0, 0, 0], "give": [2, 0, 2, 1, 1]}, {"take": [0, 2, 0, 0, 0], "give": [0, 0, 0, 0, 0]}], "start": [2, 2, 2, 2, 2], "queries": [[0, 2, 4, 3, 0], [0, 1, 2, 100, 2], [3, 2, 3, 1, 4], [0, 100, 2, 1, 2], [4, 4, 4, 2, 2], [2, 0, 5, 1, 4], [4, 1, 1, 0, 2], [1, 1, 0, 0, 4]]},
    {"counters": 4, "rules": [{"take": [0, 0, 1, 1], "give": [0, 1, 0, 0]}, {"take": [0, 0, 0, 0], "give": [2, 2, 0, 0]}, {"take": [0, 2, 0, 1], "give": [2, 2, 0, 0]}, {"take": [0, 0, 2, 0], "give": [2, 0, 2, 0]}], "start": [0, 0, 1, 2], "queries": [[0, 100, 1, 1], [0, 1, 0, 1], [0, 1, 0, 1], [1, 1, 4, 1], [2, 2, 1, 2]]},
    {"counters": 4, "rules": [{"take": [0, 0, 2, 2], "give": [1, 2, 1, 0]}, {"take": [0, 1, 1, 0], "give": [1, 0, 0, 1]}, {"take": [2, 0, 0, 0], "give": [2, 0, 0, 1]}, {"take": [1, 0, 0, 0], "give": [0, 1, 0, 0]}, {"take": [2, 1, 0, 0], "give": [2, 0, 0, 2]}, {"take": [0, 0, 1, 0], "give": [1, 0, 0, 0]}], "start": [1, 2, 2, 1], "queries": [[4, 3, 3, 2], [1, 2, 0, 5], [3, 4, 4, 0], [1, 4, 2, 3], [0, 4, 1, 2], [1, 4, 1, 0], [3, 0, 4, 2]]},
    {"counters": 4, "rules": [{"take": [0, 0, 1, 1], "give": [2, 0, 0, 0]}, {"take": [0, 0, 1, 0], "give": [1, 0, 0, 0]}, {"take": [0, 0, 2, 1], "give": [0, 2, 0, 1]}, {"take": [0, 1, 0, 0], "give": [1, 0, 0, 1]}, {"take": [1, 0, 1, 0], "give": [2, 2, 1, 2]}], "start": [2, 0, 2, 2], "queries": [[4, 3, 3, 1], [3, 1, 1, 2], [5, 0, 0, 0], [4, 0, 1, 4], [3, 1, 0, 3], [1, 1, 0, 0], [20, 2, 2, 2], [0, 700, 1, 0]]},
    {"counters": 4, "rules": [{"take": [0, 1, 2, 0], "give": [1, 1, 0, 1]}, {"take": [0, 0, 0, 0], "give": [1, 1, 0, 0]}, {"take": [0, 0, 1, 1], "give": [0, 0, 0, 2]}, {"take": [1, 2, 2, 0], "give": [0, 0, 1, 0]}, {"take": [0, 0, 2, 0], "give": [0, 2, 1, 0]}, {"take": [0, 2, 1, 1], "give": [0, 0, 0, 0]}], "start": [2, 1, 2, 2], "queries": [[3, 4, 2, 2], [2, 4, 2, 1], [2, 1, 0, 1], [4, 4, 1, 4], [2, 1, 0, 4], [3, 1, 3, 0], [4, 0, 1, 3]]},
    {"counters": 5, "rules": [{"take": [0, 0, 0, 1, 0], "give": [1, 2, 0, 2, 0]}, {"take": [2, 0, 1, 0, 2], "give": [0, 0, 0, 0, 0]}, {"take": [0, 0, 0, 1, 1], "give": [0, 2, 1, 2, 0]}, {"take": [2, 1, 0, 0, 2], "give": [1, 0, 2, 1, 2]}, {"take": [0, 0, 2, 0, 0], "give": [0, 0, 0, 0, 0]}, {"take": [2, 0, 0, 0, 2], "give": [1, 0, 0, 0, 1]}], "start": [2, 2, 1, 2, 2], "queries": [[1, 3, 4, 0, 2], [1, 2, 0, 700, 1], [2, 6, 1, 4, 0], [0, 1, 1, 0, 3], [1, 2, 100, 0, 0], [0, 0, 3, 4, 2], [3, 5, 1, 7, 0]]},
    {"counters": 4, "rules": [{"take": [0, 1, 0, 0], "give": [2, 1, 0, 0]}, {"take": [0, 1, 2, 0], "give": [0, 0, 0, 2]}, {"take": [0, 2, 2, 0], "give": [2, 0, 1, 1]}, {"take": [1, 0, 0, 0], "give": [2, 0, 1, 1]}, {"take": [1, 0, 0, 1], "give": [0, 0, 0, 1]}, {"take": [0, 1, 0, 0], "give": [2, 0, 0, 2]}], "start": [1, 1, 2, 0], "queries": [[1, 0, 1, 1], [1, 0, 0, 2], [1, 3, 2, 0], [0, 0, 0, 2], [0, 0, 0, 2], [2, 1, 100, 2], [100, 1, 1, 2], [0, 1, 0, 20]]},
    {"counters": 4, "rules": [{"take": [0, 1, 2, 0], "give": [0, 0, 0, 0]}, {"take": [2, 0, 0, 1], "give": [0, 0, 0, 2]}, {"take": [2, 0, 0, 0], "give": [2, 0, 0, 1]}, {"take": [0, 0, 1, 0], "give": [0, 2, 0, 2]}], "start": [2, 0, 2, 2], "queries": [[0, 5, 0, 7], [100, 1, 2, 2], [2, 2, 1, 5], [0, 2, 1, 5], [2, 4, 1, 4], [0, 4, 0, 7], [4, 2, 1, 0], [3, 2, 4, 1]]},
    {"counters": 4, "rules": [{"take": [0, 0, 2, 2], "give": [0, 0, 2, 0]}, {"take": [0, 2, 1, 0], "give": [0, 0, 1, 1]}, {"take": [0, 0, 2, 0], "give": [1, 1, 0, 0]}, {"take": [1, 2, 2, 2], "give": [2, 0, 0, 0]}, {"take": [0, 0, 0, 0], "give": [2, 1, 0, 2]}, {"take": [0, 0, 1, 2], "give": [1, 0, 0, 1]}], "start": [2, 2, 2, 0], "queries": [[0, 4, 4, 3], [4, 0, 2, 1], [3, 3, 2, 0], [2, 0, 3, 2], [2, 0, 2, 1], [1, 2, 2, 700], [1, 4, 1, 0]]},
    {"counters": 3, "rules": [{"take": [0, 2, 2], "give": [0, 0, 0]}, {"take": [0, 2, 0], "give": [2, 0, 0]}, {"take": [1, 1, 0], "give": [2, 0, 1]}, {"take": [2, 2, 0], "give": [0, 0, 0]}], "start": [2, 2, 0], "queries": [[3, 1, 4], [4, 0, 0], [0, 0, 0], [1, 1, 100], [3, 0, 2], [4, 0, 3], [2, 20, 0], [100, 0, 0]]},
    {"counters": 3, "rules": [{"take": [0, 2, 1], "give": [1, 0, 1]}, {"take": [1, 0, 0], "give": [0, 2, 0]}, {"take": [0, 1, 2], "give": [0, 2, 1]}, {"take": [0, 0, 0], "give": [2, 1, 0]}], "start": [0, 1, 2], "queries": [[700, 0, 0], [2, 3, 1], [1, 700, 2], [4, 3, 1], [3, 0, 1], [700, 1, 0], [0, 3, 4]]},
    {"counters": 4, "rules": [{"take": [0, 1, 0, 1], "give": [2, 0, 1, 0]}, {"take": [0, 0, 0, 0], "give": [0, 0, 0, 1]}, {"take": [0, 0, 0, 0], "give": [1, 0, 1, 0]}, {"take": [1, 2, 0, 0], "give": [0, 0, 0, 1]}, {"take": [0, 2, 2, 0], "give": [0, 0, 0, 2]}], "start": [1, 1, 2, 1], "queries": [[5, 0, 3, 0], [0, 4, 1, 2], [2, 20, 0, 2], [3, 1, 1, 2], [3, 0, 3, 0], [3, 2, 4, 3], [2, 1, 3, 1], [4, 4, 1, 0]]},
    {"counters": 5, "rules": [{"take": [1, 0, 2, 0, 0], "give": [1, 0, 0, 0, 0]}, {"take": [1, 0, 0, 0, 0], "give": [1, 1, 0, 0, 0]}, {"take": [0, 2, 1, 0, 0], "give": [0, 0, 0, 2, 0]}, {"take": [1, 1, 0, 2, 0], "give": [0, 0, 0, 1, 0]}, {"take": [1, 0, 0, 0, 0], "give": [2, 0, 0, 1, 2]}], "start": [2, 2, 1, 1, 2], "queries": [[4, 4, 4, 4, 0], [2, 1, 20, 0, 0], [2, 2, 2, 1, 20], [1, 2, 2, 20, 0]]},
    {"counters": 3, "rules": [{"take": [0, 2, 0], "give": [0, 0, 0]}, {"take": [0, 2, 0], "give": [2, 0, 2]}, {"take": [0, 0, 1], "give": [0, 1, 0]}, {"take": [0, 0, 2], "give": [2, 1, 0]}, {"take": [0, 2, 1], "give": [2, 0, 1]}, {"take": [2, 0, 0], "give": [2, 0, 0]}], "start": [2, 1, 2], "queries": [[3, 4, 3], [6, 0, 0], [2, 3, 0], [100, 0, 1], [2, 1, 700]]},
    {"counters": 4, "rules": [{"take": [2, 0, 1, 0], "give": [1, 2, 0, 2]}, {"take": [0, 0, 1, 0], "give": [0, 2, 0, 1]}, {"take": [0, 0, 0, 2], "give": [0, 1, 2, 1]}, {"take": [2, 0, 0, 0], "give": [0, 2, 1, 0]}], "start": [2, 1, 1, 0], "queries": [[2, 2, 1, 20], [2, 4, 3, 1], [20, 0, 2, 2]]},
    {"counters": 2, "rules": [{"take": [1, 1], "give": [2, 0]}, {"take": [0, 1], "give": [2, 0]}, {"take": [0, 0], "give": [0, 0]}], "start": [2, 1], "queries": [[0, 4], [0, 1], [4, 1], [5, 0], [3, 0], [100, 2], [5, 0]]},
    {"counters": 4, "rules": [{"take": [0, 0, 0, 1], "give": [2, 0, 0, 0]}, {"take": [0, 1, 2, 0], "give": [0, 0, 2, 1]}, {"take": [1, 0, 1, 0], "give": [1, 0, 1, 1]}, {"take": [1, 0, 0, 0], "give": [0, 0, 0, 2]}], "start": [1, 1, 2, 0], "queries": [[1, 2, 2, 0], [0, 100, 1, 0], [1, 1, 2, 0], [1, 3, 3, 1], [3, 4, 1, 4], [0, 1, 2, 0]]},
    {"counters": 5, "rules": [{"take": [0, 1, 2, 2, 0], "give": [1, 0, 1, 2, 0]}, {"take": [2, 0, 0, 0, 0], "give": [0, 0, 1, 0, 2]}, {"take": [0, 0, 0, 1, 0], "give": [0, 0, 0, 0, 2]}, {"take": [2, 1, 2, 2, 0], "give": [2, 1, 0, 0, 0]}, {"take": [0, 0, 0, 0, 0], "give": [1, 2, 0, 0, 0]}], "start": [1, 1, 2, 1, 2], "queries": [[2, 1, 3, 1, 4], [1, 1, 2, 0, 4], [1, 1, 2, 1, 3], [3, 3, 2, 2, 4]]},
    {"counters": 4, "rules": [{"take": [1, 0, 2, 0], "give": [0, 1, 1, 0]}, {"take": [0, 1, 0, 0], "give": [0, 1, 0, 2]}, {"take": [0, 1, 2, 1], "give": [0, 2, 2, 0]}, {"take": [0, 1, 0, 2], "give": [1, 2, 0, 0]}, {"take": [0, 1, 0, 2], "give": [0, 0, 0, 0]}, {"take": [0, 0, 1, 0], "give": [0, 0, 0, 1]}], "start": [2, 0, 2, 1], "queries": [[1, 0, 0, 0], [2, 1, 0, 3], [1, 0, 4, 0]]},
]


def _rand_system(rng):
    n = rng.randint(2, 5)
    nrules = rng.randint(1, 6)
    rules = []
    for _ in range(nrules):
        take = [0] * n
        give = [0] * n
        for i in range(n):
            r = rng.random()
            if r < 0.35:
                take[i] = rng.randint(1, 2)
            r = rng.random()
            if r < 0.4:
                give[i] = rng.randint(1, 2)
        rules.append(_rule(take, give))
    start = [rng.randint(0, 2) for _ in range(n)]
    if sum(start) == 0:
        start[rng.randrange(n)] = 1
    return {"counters": n, "rules": rules, "start": start, "queries": []}


def _rand_queries(rng, job, marks):
    n = job["counters"]
    qs = []
    finite = [m for m in marks if OMEGA not in m]
    for _ in range(rng.randint(3, 8)):
        style = rng.random()
        if style < 0.45 and finite:
            base = list(rng.choice(finite))
            for i in range(n):
                if rng.random() < 0.3:
                    base[i] = max(0, base[i] + rng.randint(-1, 2))
            qs.append([min(x, VAL_MAX) for x in base])
        elif style < 0.75:
            qs.append([rng.randint(0, 4) for _ in range(n)])
        else:
            q = [rng.randint(0, 2) for _ in range(n)]
            q[rng.randrange(n)] = rng.choice([20, 100, 700])
            qs.append(q)
    return qs


def build_battery(systems=55):
    rng = random.Random(0xC0FE7C)
    cases = []
    for job in hand_cases() + TRAP_SYSTEMS:
        cases.append((job, ref_run(job)))
    made = 0
    while made < systems:
        job = _rand_system(rng)
        try:
            marks = km_markings(job["counters"],
                                [(r["take"], r["give"]) for r in job["rules"]],
                                job["start"], budget=20000)
        except RuntimeError:
            continue
        job["queries"] = _rand_queries(rng, job, marks)
        if not job["queries"]:
            continue
        cases.append((job, ref_run(job)))
        made += 1
    return cases


# --------------------------------------------------------------------------
# integrity + build
# --------------------------------------------------------------------------
def _restore_pinned():
    for root, _dirs, files in os.walk(PINNED):
        for name in files:
            src = os.path.join(root, name)
            rel = os.path.relpath(src, PINNED)
            dst = os.path.join(APP, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)


def _imported_paths(src):
    """Extract the import paths actually declared by the source, covering
    plain, aliased, blank, and dot imports in both single-line and block form.
    This matches real import statements rather than bare tokens anywhere in the
    text, so an ordinary identifier that happens to spell a package name is not
    mistaken for an import."""
    paths = set()
    for m in re.finditer(r'^\s*import\s+(?:[A-Za-z0-9_.]+\s+)?"([^"]+)"',
                         src, flags=re.MULTILINE):
        paths.add(m.group(1))
    for block in re.findall(r"import\s*\((.*?)\)", src, flags=re.DOTALL):
        for m in re.finditer(r'(?:[A-Za-z0-9_.]+\s+)?"([^"]+)"', block):
            paths.add(m.group(1))
    return paths


def _check_editable():
    path = os.path.join(APP, "analysis", "analysis.go")
    assert os.path.exists(path), "analysis/analysis.go missing"
    src = open(path, encoding="utf-8").read()
    for imp in _imported_paths(src):
        forbidden = any(imp == root or imp.startswith(root + "/")
                        for root in FORBIDDEN_IMPORT_ROOTS)
        assert not forbidden, "disallowed import in analysis.go: %s" % imp


def _check_no_extra_go():
    found = set()
    for root, _dirs, files in os.walk(APP):
        for name in files:
            if name.endswith(".go"):
                rel = os.path.relpath(os.path.join(root, name), APP).replace(os.sep, "/")
                found.add(rel)
    extra = found - ALLOWED_GO_FILES
    assert not extra, "unexpected Go file(s): %s" % sorted(extra)


_BIN = None


def build_binary():
    global _BIN
    if _BIN is not None:
        return _BIN
    _restore_pinned()
    _check_no_extra_go()
    _check_editable()
    out = os.path.join(APP, "coverd_bin")
    env = dict(os.environ, GOFLAGS="-mod=mod", CGO_ENABLED="0", GO111MODULE="on")
    p = subprocess.run(["go", "build", "-o", out, "."], cwd=APP, env=env,
                       capture_output=True, text=True)
    assert p.returncode == 0, "go build failed:\n%s\n%s" % (p.stdout, p.stderr)
    _BIN = out
    return _BIN


def run_binary(binp, job):
    try:
        p = subprocess.run([binp], input=json.dumps(job), capture_output=True,
                           text=True, encoding="utf-8", timeout=30)
    except subprocess.TimeoutExpired:
        return {"timeout": True}
    assert p.returncode == 0, "binary exited %d: %s" % (p.returncode, p.stderr)
    try:
        return json.loads(p.stdout)
    except ValueError:
        raise AssertionError("output is not valid JSON: %r" % p.stdout[:200])


# --------------------------------------------------------------------------
# tests
# --------------------------------------------------------------------------
def test_build_and_integrity():
    """Restore pinned sources, enforce the analysis import/identifier and no-extra-Go rules, and build the agent binary offline."""
    assert build_binary()


def test_battery():
    """Every counter system in the hidden battery must receive exactly the reference cover verdicts for all its queries, within the per-case time limit; the score is all-or-nothing."""
    binp = build_binary()
    battery = build_battery()
    failures = []
    for i, (job, expected) in enumerate(battery):
        got = run_binary(binp, job)
        if got != expected:
            failures.append((i, json.dumps(job)[:110],
                             json.dumps(expected)[:110], json.dumps(got)[:110]))
    if failures:
        msg = "\n".join(
            "  case#%d job=%s\n    expected=%s\n    got=%s" % f
            for f in failures[:10])
        raise AssertionError(
            "%d/%d battery cases wrong:\n%s" % (len(failures), len(battery), msg))

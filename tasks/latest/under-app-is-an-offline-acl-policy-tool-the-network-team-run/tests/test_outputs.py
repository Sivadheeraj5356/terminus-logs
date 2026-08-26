"""End-to-end checks for the ACL evaluator.

Everything runs through subprocess: build the binary from /app, then drive
`evaluate` and `lint` over a WITHHELD fixture set under /tests/fixtures and
assert on the JSON. The graded fixtures are NOT the developer samples the agent
sees in /app/testdata; they exercise edge-case rule interactions the samples do
not, so matching /app/testdata is not the same as passing. Expected values were
worked out by hand from the fixtures, the priority ordering, and the CIDR math,
and the two outputs are cross-checked against each other, so you cannot pass by
dumping a file or hardcoding a constant.
"""

import json
import subprocess
import tempfile
from pathlib import Path

APP = Path("/app")
BIN = None

FIX = Path("/tests/fixtures")
RULES_MAIN = str(FIX / "graded_main.json")
FLOWS_MAIN = str(FIX / "graded_main.ndjson")
RULES_EDGE = str(FIX / "graded_edge.json")
FLOWS_EDGE = str(FIX / "graded_edge.ndjson")
RULES_BAD = str(FIX / "graded_bad.json")
FLOWS_BAD = str(FIX / "graded_bad.ndjson")
RULES_CLEAN = str(FIX / "graded_clean.json")
FLOWS_CLEAN = str(FIX / "graded_clean.ndjson")


def _binary() -> str:
    global BIN
    if BIN is None:
        binPath = Path(tempfile.mkdtemp()) / "acl"
        proc = subprocess.run(
            ["go", "build", "-o", str(binPath), "./cmd/acl"],
            cwd=APP, capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        BIN = str(binPath)
    return BIN


def _evaluate(rules: str, flows: str) -> dict:
    args = [_binary(), "evaluate", "--rules", rules, "--flows", flows]
    proc = subprocess.run(args, cwd=APP, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _lint(rules: str, flows: str | None = None) -> dict:
    args = [_binary(), "lint", "--rules", rules]
    if flows is not None:
        args += ["--flows", flows]
    proc = subprocess.run(args, cwd=APP, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


# ----- build / unit smoke -----

def test_module_builds() -> None:
    """The Go module compiles cleanly with `go build ./...`."""
    proc = subprocess.run(["go", "build", "./..."], cwd=APP,
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


# ----- evaluate: order, priority ordering, log attribution, default deny -----

def test_decisions_in_input_order() -> None:
    """Decisions come back in the same order the flows were read."""
    rep = _evaluate(RULES_MAIN, FLOWS_MAIN)
    srcs = [d["src"] for d in rep["decisions"]]
    assert srcs == [
        "172.20.5.5", "172.16.5.5", "8.8.8.8", "8.8.8.8",
        "172.16.9.9", "172.16.9.9", "8.8.8.8", "300.1.1.1",
    ]


def test_priority_ordering_beats_file_order() -> None:
    """A lab web flow is denied by the higher-priority deny even though a
    broader allow sits EARLIER in the file. The deny (file index 3, priority
    700) outranks allow-web (file index 2, priority 400)."""
    rep = _evaluate(RULES_MAIN, FLOWS_MAIN)
    rules = json.loads(Path(RULES_MAIN).read_text())
    idx = {r["id"]: i for i, r in enumerate(rules)}
    assert idx["allow-web"] < idx["deny-web-lab"]  # broad allow earlier in file
    d = rep["decisions"][0]
    assert d["decision"] == "deny" and d["matched"] == "deny-web-lab"
    # the non-lab web flow is not in the deny block, so it is allowed.
    d1 = rep["decisions"][1]
    assert d1["decision"] == "allow" and d1["matched"] == "allow-web"


def test_log_rules_recorded_then_terminal_decides() -> None:
    """A flow that crosses log rules records them all, in order, before the
    terminal decision, which is the one reported in `matched`."""
    rep = _evaluate(RULES_MAIN, FLOWS_MAIN)
    assert rep["decisions"][0]["logged"] == ["log-web", "log-web-2"]
    assert rep["decisions"][1]["logged"] == ["log-web", "log-web-2"]
    # http flows cross no log rule (log rules are 443/tcp/inbound only).
    assert rep["decisions"][2]["logged"] == []
    assert rep["decisions"][2]["decision"] == "allow"
    assert rep["decisions"][2]["matched"] == "allow-http"


def test_shadowed_rule_never_decides() -> None:
    """The http flow to the .192/26 subnet is allowed by allow-http; the
    shadowed deny-http-sub never gets to decide it."""
    rep = _evaluate(RULES_MAIN, FLOWS_MAIN)
    d = rep["decisions"][3]
    assert d["decision"] == "allow" and d["matched"] == "allow-http"


def test_canonicalized_rule_still_matches() -> None:
    """The egress rule written 172.16.9.9/12 matches via its canonical
    172.16.0.0/12 block for an outbound 22 flow."""
    rep = _evaluate(RULES_MAIN, FLOWS_MAIN)
    d = rep["decisions"][5]
    assert d["decision"] == "allow" and d["matched"] == "allow-egress"


def test_default_deny_sentinel_and_logged_carry() -> None:
    """An unmatched flow is denied with the default-deny sentinel, and any log
    rule crossed on the way is still recorded."""
    rep = _evaluate(RULES_MAIN, FLOWS_MAIN)
    # 8.8.8.8 -> 443: crosses the log rules, matches no terminal rule.
    d6 = rep["decisions"][6]
    assert d6["decision"] == "deny"
    assert d6["matched"] == "default-deny"
    assert d6["logged"] == ["log-web", "log-web-2"]
    # unparseable src: default deny, no rules consulted, empty log list.
    d7 = rep["decisions"][7]
    assert d7["decision"] == "deny"
    assert d7["matched"] == "default-deny"
    assert d7["logged"] == []


def test_default_match_is_documented_string_not_null() -> None:
    """matched is always a string; the default is the sentinel, never null/empty."""
    rep = _evaluate(RULES_MAIN, FLOWS_MAIN)
    for d in rep["decisions"]:
        assert isinstance(d["matched"], str) and d["matched"] != ""
    denies = [d for d in rep["decisions"] if d["matched"] == "default-deny"]
    assert len(denies) == 2


def test_evaluate_summary_counts() -> None:
    """Summary allow/deny/flagged/total reconcile with the decisions."""
    rep = _evaluate(RULES_MAIN, FLOWS_MAIN)
    s = rep["summary"]
    assert s == {"allow": 5, "deny": 3, "flagged": 3, "total": 8}
    for v in s.values():
        assert isinstance(v, int) and not isinstance(v, bool)
    assert s["allow"] + s["deny"] == s["total"]
    flagged = sum(1 for d in rep["decisions"] if d["logged"])
    assert s["flagged"] == flagged


def test_evaluate_key_sets_exact() -> None:
    """Top-level and decision-object key sets are exactly as documented."""
    rep = _evaluate(RULES_MAIN, FLOWS_MAIN)
    assert set(rep.keys()) == {"decisions", "summary"}
    for d in rep["decisions"]:
        assert set(d.keys()) == {
            "src", "dst", "port", "protocol", "direction",
            "decision", "matched", "logged",
        }
        assert d["decision"] in ("allow", "deny")
        assert isinstance(d["port"], int) and not isinstance(d["port"], bool)
        assert isinstance(d["logged"], list)


def test_dropped_rules_excluded_from_evaluate_keep_id() -> None:
    """Survivors keep their identity after invalid rules are dropped: the
    survivor at file index 7 decides the ssh flow, the survivor at index 0 the
    web flow, though six malformed rules sit between them."""
    rep = _evaluate(RULES_BAD, FLOWS_BAD)
    assert rep["decisions"][0]["matched"] == "ok-hi"
    assert rep["decisions"][1]["matched"] == "ok-lo"


# ----- evaluate: edge-case rule interactions -----

def test_equal_priority_tie_break_in_evaluate() -> None:
    """Two rules with equal priority (700) overlap; the lower file index is
    consulted first, so the deny at index 0 decides, not the allow at index 1."""
    rep = _evaluate(RULES_EDGE, FLOWS_EDGE)
    d = rep["decisions"][0]
    assert d["decision"] == "deny" and d["matched"] == "tie-deny"


def test_canonicalized_rule_covered_still_defers_to_coverer() -> None:
    """canon-lo is written 10.5.5.5/8; a matching flow is decided by cover-hi,
    the canonical-equal higher-priority rule ahead of it."""
    rep = _evaluate(RULES_EDGE, FLOWS_EDGE)
    d = rep["decisions"][1]
    assert d["decision"] == "allow" and d["matched"] == "cover-hi"


def test_shadowed_log_rule_never_fires_but_earlier_logs_do() -> None:
    """The port-80 flow crosses log-a and log-a-dup, then deny-block decides;
    log-b (shadowed by deny-block) never appears in the log list."""
    rep = _evaluate(RULES_EDGE, FLOWS_EDGE)
    d = rep["decisions"][2]
    assert d["decision"] == "deny" and d["matched"] == "deny-block"
    assert d["logged"] == ["log-a", "log-a-dup"]
    assert "log-b" not in d["logged"]


def test_port_range_boundaries_inclusive() -> None:
    """The [100,200] range matches exactly at both ends and rejects one step
    beyond either end."""
    rep = _evaluate(RULES_EDGE, FLOWS_EDGE)
    at_min = rep["decisions"][3]
    at_max = rep["decisions"][4]
    just_over = rep["decisions"][5]
    just_under = rep["decisions"][6]
    assert at_min["port"] == 100 and at_min["matched"] == "port-edge"
    assert at_max["port"] == 200 and at_max["matched"] == "port-edge"
    assert just_over["port"] == 201 and just_over["matched"] == "default-deny"
    assert just_under["port"] == 99 and just_under["matched"] == "default-deny"


def test_edge_summary_counts() -> None:
    """The edge batch reconciles: three allows, four denies, one flagged."""
    rep = _evaluate(RULES_EDGE, FLOWS_EDGE)
    assert rep["summary"] == {"allow": 3, "deny": 4, "flagged": 1, "total": 7}


# ----- lint: parse-phase warnings + per-reason tally (propagation path A) -----

def test_load_warnings_surface_with_index_code_detail() -> None:
    """Every load-time reason code reaches lint.warnings with index and detail,
    including two bad_cidr on one index (src before dst) and three problems on
    another (a rule that trips more than one check)."""
    lint = _lint(RULES_BAD, FLOWS_BAD)
    entries = [(w["index"], w["code"], w["detail"]) for w in lint["warnings"]]
    assert (1, "bad_id", "(empty)") in entries
    assert (2, "dup_id", "ok-lo") in entries
    assert (3, "bad_cidr", "10.0.0.0/33") in entries
    assert (3, "bad_cidr", "400.0.0.0/16") in entries
    assert (4, "bad_action", "permit") in entries
    assert (4, "bad_port", "90-80") in entries
    assert (4, "bad_proto", "sctp") in entries
    assert (5, "bad_direction", "sideways") in entries
    assert (6, "bad_priority", "-5") in entries
    # src bad_cidr recorded before dst bad_cidr on the same index.
    cidr3 = [w["detail"] for w in lint["warnings"]
             if w["index"] == 3 and w["code"] == "bad_cidr"]
    assert cidr3 == ["10.0.0.0/33", "400.0.0.0/16"]


def test_by_reason_tally_reconciles_with_warnings() -> None:
    """by_reason tallies the warnings and its values sum to the warning count."""
    lint = _lint(RULES_BAD, FLOWS_BAD)
    assert lint["by_reason"] == {
        "bad_id": 1, "dup_id": 1, "bad_cidr": 2, "bad_port": 1,
        "bad_action": 1, "bad_proto": 1, "bad_direction": 1, "bad_priority": 1,
    }
    assert sum(lint["by_reason"].values()) == len(lint["warnings"])


def test_warnings_sorted_by_index_then_code() -> None:
    """warnings are sorted by index ascending, ties broken by code ascending."""
    lint = _lint(RULES_BAD, FLOWS_BAD)
    keys = [(w["index"], w["code"]) for w in lint["warnings"]]
    assert keys == sorted(keys)


# ----- lint: canonicalization surfaced (propagation path B) -----

def test_normalized_note_carries_canonical_cidr() -> None:
    """A non-canonical rule loads and surfaces a normalized note holding the
    canonical block string, and does not count as dropped."""
    lint = _lint(RULES_MAIN, FLOWS_MAIN)
    norm = [w for w in lint["warnings"] if w["code"] == "normalized"]
    assert norm == [{"index": 7, "code": "normalized", "detail": "172.16.0.0/12"}]
    assert lint["by_reason"].get("normalized") == 1
    assert lint["summary"]["dropped"] == 0


def test_normalized_note_on_a_shadowed_rule() -> None:
    """canon-lo is both normalized (10.5.5.5/8 -> 10.0.0.0/8) AND shadowed by
    cover-hi: the note surfaces even though the rule is dead."""
    lint = _lint(RULES_EDGE, FLOWS_EDGE)
    norm = [w for w in lint["warnings"] if w["code"] == "normalized"]
    assert norm == [{"index": 3, "code": "normalized", "detail": "10.0.0.0/8"}]
    assert {"index": 3, "detail": "2"} in lint["shadowed"]


# ----- lint: analysis-phase findings (propagation path C) -----

def test_shadowed_redundant_unreachable_findings() -> None:
    """The three analysis buckets carry the right indices and details."""
    lint = _lint(RULES_MAIN, FLOWS_MAIN)
    assert lint["shadowed"] == [{"index": 5, "detail": "4"}]
    assert lint["redundant"] == [{"index": 1, "detail": "0"}]
    assert lint["unreachable"] == [{"index": 8, "detail": ""}]


def test_edge_findings_shadowed_precedence_and_tie_break() -> None:
    """The edge ruleset: an equal-priority rule shadowed via the file-index
    tie-break (1 by 0), a canonicalized rule shadowed by its canonical-equal
    coverer (3 by 2), a log rule shadowed by an earlier terminal (7 by 6), and a
    duplicate log that is only redundant because nothing covers it (5 by 4)."""
    lint = _lint(RULES_EDGE, FLOWS_EDGE)
    assert lint["shadowed"] == [
        {"index": 1, "detail": "0"},
        {"index": 3, "detail": "2"},
        {"index": 7, "detail": "6"},
    ]
    assert lint["redundant"] == [{"index": 5, "detail": "4"}]
    assert lint["unreachable"] == []
    assert lint["summary"] == {"rules": 9, "reachable": 5, "shadowed": 3,
                               "redundant": 1, "unreachable": 0, "dropped": 0}


def test_lint_summary_partitions_loaded_rules() -> None:
    """summary partitions the loaded rules and reconciles with the arrays."""
    lint = _lint(RULES_MAIN, FLOWS_MAIN)
    s = lint["summary"]
    assert s == {"rules": 9, "reachable": 6, "shadowed": 1,
                 "redundant": 1, "unreachable": 1, "dropped": 0}
    assert s["reachable"] + s["shadowed"] + s["redundant"] + s["unreachable"] == s["rules"]
    assert s["shadowed"] == len(lint["shadowed"])
    assert s["redundant"] == len(lint["redundant"])
    assert s["unreachable"] == len(lint["unreachable"])


def test_lint_bad_summary_counts_dropped() -> None:
    """On the ruleset with six bad rules, summary counts survivors and drops."""
    lint = _lint(RULES_BAD, FLOWS_BAD)
    s = lint["summary"]
    assert s["rules"] == 2
    assert s["dropped"] == 6
    dropping = {w["index"] for w in lint["warnings"] if w["code"] != "normalized"}
    assert s["dropped"] == len(dropping)


def test_lint_without_flows_marks_live_rules_unreachable() -> None:
    """Without --flows every live, non-shadowed, non-redundant rule is
    unreachable, while shadowing and redundancy stay structural."""
    lint = _lint(RULES_MAIN)
    assert [e["index"] for e in lint["shadowed"]] == [5]
    assert [e["index"] for e in lint["redundant"]] == [1]
    assert [e["index"] for e in lint["unreachable"]] == [0, 2, 3, 4, 6, 7, 8]
    assert lint["summary"] == {"rules": 9, "reachable": 0, "shadowed": 1,
                               "redundant": 1, "unreachable": 7, "dropped": 0}


# ----- lint shape / empties / keys -----

def test_lint_key_sets_exact() -> None:
    """lint has exactly the six documented keys and the summary six keys."""
    lint = _lint(RULES_MAIN, FLOWS_MAIN)
    assert set(lint.keys()) == {
        "warnings", "by_reason", "shadowed", "redundant", "unreachable", "summary",
    }
    assert set(lint["summary"].keys()) == {
        "rules", "reachable", "shadowed", "redundant", "unreachable", "dropped",
    }


def test_lint_entry_types_and_sorting() -> None:
    """Finding entries are {index:int, detail:str}, sorted by index ascending."""
    lint = _lint(RULES_EDGE, FLOWS_EDGE)
    for key in ("shadowed", "redundant", "unreachable"):
        idx = [e["index"] for e in lint[key]]
        assert idx == sorted(idx), key
        for e in lint[key]:
            assert set(e.keys()) == {"index", "detail"}
            assert isinstance(e["index"], int) and not isinstance(e["index"], bool)
            assert isinstance(e["detail"], str)
    for w in lint["warnings"]:
        assert set(w.keys()) == {"index", "code", "detail"}


def test_clean_ruleset_has_empty_arrays_and_object() -> None:
    """A clean ruleset yields empty warning/finding arrays and an empty tally."""
    lint = _lint(RULES_CLEAN, FLOWS_CLEAN)
    assert lint["warnings"] == []
    assert lint["by_reason"] == {}
    for key in ("shadowed", "redundant", "unreachable"):
        assert lint[key] == [], key
    assert lint["summary"] == {"rules": 1, "reachable": 1, "shadowed": 0,
                               "redundant": 0, "unreachable": 0, "dropped": 0}


# ----- cross-subcommand consistency -----

def test_evaluate_and_lint_agree_on_dead_rules() -> None:
    """A rule lint calls shadowed/redundant/unreachable is never a terminal
    matched id in evaluate; every matched id is a reachable rule."""
    ev = _evaluate(RULES_MAIN, FLOWS_MAIN)
    lint = _lint(RULES_MAIN, FLOWS_MAIN)

    rules = json.loads(Path(RULES_MAIN).read_text())
    id_of = {r["id"]: i for i, r in enumerate(rules)}

    matched_idx = {id_of[d["matched"]] for d in ev["decisions"]
                   if d["matched"] != "default-deny"}
    dead = set()
    for key in ("shadowed", "redundant", "unreachable"):
        dead |= {e["index"] for e in lint[key]}

    assert matched_idx.isdisjoint(dead), (matched_idx, dead)
    assert matched_idx == {2, 3, 4, 6, 7}


def test_evaluate_and_lint_agree_on_dead_rules_edge() -> None:
    """Same consistency invariant on the edge ruleset, where the dead set spans
    a tie-break shadow, a canonical-equal shadow, a shadowed log, and a
    redundant log."""
    ev = _evaluate(RULES_EDGE, FLOWS_EDGE)
    lint = _lint(RULES_EDGE, FLOWS_EDGE)

    rules = json.loads(Path(RULES_EDGE).read_text())
    id_of = {r["id"]: i for i, r in enumerate(rules)}

    matched_idx = {id_of[d["matched"]] for d in ev["decisions"]
                   if d["matched"] != "default-deny"}
    dead = set()
    for key in ("shadowed", "redundant", "unreachable"):
        dead |= {e["index"] for e in lint[key]}

    assert matched_idx.isdisjoint(dead), (matched_idx, dead)
    assert matched_idx == {0, 2, 6, 8}
    assert dead == {1, 3, 5, 7}


# ----- config read at run time: mutation test -----

def test_rules_flag_is_read_at_runtime() -> None:
    """Insert a high-priority deny at the front of a copied ruleset and point
    --rules at it: one flow flips allow->deny in evaluate and lint re-derives
    shadowing against the mutated file."""
    baseline = _evaluate(RULES_MAIN, FLOWS_MAIN)
    assert baseline["decisions"][1]["decision"] == "allow"
    assert baseline["decisions"][1]["matched"] == "allow-web"

    rules = json.loads(Path(RULES_MAIN).read_text())
    rules.insert(0, {
        "id": "blk", "action": "deny",
        "src": "172.16.0.0/12", "dst": "10.10.0.0/16",
        "port_min": 443, "port_max": 443,
        "protocol": "tcp", "direction": "inbound", "priority": 800,
    })
    mutated = Path(tempfile.mkdtemp()) / "rules.json"
    mutated.write_text(json.dumps(rules))

    mut = _evaluate(str(mutated), FLOWS_MAIN)
    assert mut["decisions"][1]["decision"] == "deny"
    assert mut["decisions"][1]["matched"] == "blk"

    base_lint = _lint(RULES_MAIN, FLOWS_MAIN)
    mut_lint = _lint(str(mutated), FLOWS_MAIN)
    assert mut_lint["summary"]["shadowed"] > base_lint["summary"]["shadowed"]

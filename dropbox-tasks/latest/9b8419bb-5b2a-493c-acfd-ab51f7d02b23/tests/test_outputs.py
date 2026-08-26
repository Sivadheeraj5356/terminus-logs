import csv
import json
import os
import pwd
import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path("/app/environment")
AGENT = "boardagent"
VERIFIER_BUILD = Path("/var/lib/verifier/build-work")
VERIFIER_BIN = Path("/var/lib/verifier/bin")
BOARDCTL = VERIFIER_BIN / "boardctl"
IXCORE = VERIFIER_BIN / "ixcore"
POLICY = ROOT / "data" / "policy_standard.json"
DECISION_ORDER = ("AUTHORIZE", "CONDITIONAL_AUTHORIZE", "POSTPONE")
SEVERITY = {"ready": 0, "watch": 1, "gap": 2, "blocked": 3}
DISSENT = {"none": 0, "minor": 1, "major": 2, "critical": 3}


def resilience_label(index: int) -> str:
    if index >= 82:
        return "strong"
    if index >= 62:
        return "guarded"
    return "fragile"


def tie_evidence(a, b):
    a_ind = a["source"] == "independent"
    b_ind = b["source"] == "independent"
    if a_ind and not b_ind:
        return a
    if b_ind and not a_ind:
        return b
    if a["note"] < b["note"]:
        return a
    if b["note"] < a["note"]:
        return b
    if a["weight"] <= b["weight"]:
        return a
    return b


def assert_memo_contract(memo, decision):
    lowered = memo.lower()
    assert "technical certification" in lowered
    assert "accepted" in lowered and "as record" in lowered
    for line in memo.strip().splitlines():
        assert line.endswith("."), f"memo line must end with period: {line!r}"
    rejected = [item for item in DECISION_ORDER if item != decision]
    compact = "Rejected alternatives: " + ",".join(rejected) + "."
    if compact not in memo:
        match = re.search(r"Rejected alternatives:\s*([A-Z_, ]+)\.", memo)
        assert match, memo
        got = [part.strip() for part in match.group(1).split(",") if part.strip()]
        assert got == rejected, got


@pytest.fixture(scope="session", autouse=True)
def verifier_hardening():
    for path in (Path("/tests"), Path("/logs/verifier")):
        if path.exists():
            try:
                os.chmod(path, 0o700)
            except OSError:
                pass
    yield


def rebuild_from_agent_source():
    if VERIFIER_BUILD.exists():
        shutil.rmtree(VERIFIER_BUILD)
    shutil.copytree(ROOT, VERIFIER_BUILD)
    os.chmod(VERIFIER_BUILD, 0o700)
    for dirpath, _dirnames, filenames in os.walk(VERIFIER_BUILD):
        os.chmod(dirpath, 0o700)
        for name in filenames:
            os.chmod(Path(dirpath) / name, 0o600)
    subprocess.run(
        [
            "cargo",
            "build",
            "--release",
            "--locked",
            "--manifest-path",
            str(VERIFIER_BUILD / "z4" / "Cargo.toml"),
        ],
        check=True,
        cwd=VERIFIER_BUILD,
    )
    VERIFIER_BIN.mkdir(parents=True, exist_ok=True)
    os.chmod(VERIFIER_BIN, 0o755)
    shutil.copy2(VERIFIER_BUILD / "z4" / "target" / "release" / "ixcore", IXCORE)
    subprocess.run(
        ["go", "build", "-o", str(BOARDCTL), "./cmd/boardctl"],
        check=True,
        cwd=VERIFIER_BUILD,
    )
    os.chmod(IXCORE, 0o755)
    os.chmod(BOARDCTL, 0o755)
    shutil.copy2(IXCORE, "/app/bin/ixcore")
    os.chmod("/app/bin/ixcore", 0o755)


def agent_ids():
    entry = pwd.getpwnam(AGENT)
    return entry.pw_uid, entry.pw_gid


def grant_agent_tree(path: Path):
    uid, gid = agent_ids()
    path = Path(path)
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        os.chown(path, uid, gid)
        os.chmod(path, 0o644)
        return
    for dirpath, _dirnames, filenames in os.walk(path):
        os.chown(dirpath, uid, gid)
        os.chmod(dirpath, 0o700)
        for name in filenames:
            fp = Path(dirpath) / name
            os.chown(fp, uid, gid)
            os.chmod(fp, 0o600)


def grant_agent_write(path: Path):
    uid, gid = agent_ids()
    path = Path(path)
    if path.exists():
        os.chown(path, uid, gid)
        os.chmod(path, 0o777 if path.is_dir() else 0o666)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chown(path.parent, uid, gid)
        os.chmod(path.parent, 0o777)


def grant_agent_read_tree(path: Path):
    path = Path(path)
    if not path.exists():
        return
    if path.is_file():
        os.chmod(path, 0o644)
        return
    for dirpath, _dirnames, filenames in os.walk(path):
        os.chmod(dirpath, 0o755)
        for name in filenames:
            os.chmod(Path(dirpath) / name, 0o644)


def prepare_agent_workspace(tmp_path: Path):
    for parent in tmp_path.parents:
        if parent == Path("/"):
            break
        if str(parent).startswith("/tmp"):
            try:
                os.chmod(parent, 0o711)
            except OSError:
                pass
    grant_agent_tree(tmp_path)


def run_review(record_dir, tmp_path, state_path=None, policy_path=POLICY, reset=False, expect_ok=True, out_name=None):
    rebuild_from_agent_source()
    prepare_agent_workspace(tmp_path)
    out_dir = tmp_path / (out_name or ("out_" + record_dir.name))
    out_dir.mkdir(exist_ok=True)
    state_path = state_path or (tmp_path / "state.json")
    grant_agent_read_tree(record_dir)
    grant_agent_read_tree(policy_path)
    grant_agent_write(out_dir)
    grant_agent_write(state_path)
    cmd = [
        "runuser",
        "-u",
        AGENT,
        "--",
        str(BOARDCTL),
        "review",
        "--record",
        str(record_dir),
        "--policy",
        str(policy_path),
        "--out",
        str(out_dir),
        "--state",
        str(state_path),
    ]
    if reset:
        cmd.append("--reset-state")
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if expect_ok:
        assert proc.returncode == 0, proc.stderr
    else:
        assert proc.returncode != 0
        assert not (out_dir / "determination.json").exists()
        assert not (out_dir / "review_journal.jsonl").exists() or (
            out_dir / "review_journal.jsonl"
        ).read_text().strip() == ""
        return proc, out_dir
    return proc, out_dir


def artifacts(out_dir):
    det = json.loads((out_dir / "determination.json").read_text())
    state = json.loads((out_dir / "board_state.json").read_text())
    memo = (out_dir / "board_memo.txt").read_text()
    rows = list(csv.DictReader((out_dir / "evidence_matrix.csv").open()))
    journal = []
    jpath = out_dir / "review_journal.jsonl"
    if jpath.exists():
        for line in jpath.read_text().splitlines():
            if line.strip():
                journal.append(json.loads(line))
    return det, rows, memo, state, journal


def merge_evidence(items):
    merged = {}
    for item in items:
        cur = merged.get(item["id"])
        if cur is None:
            merged[item["id"]] = dict(item)
            continue
        if SEVERITY[item["status"]] > SEVERITY[cur["status"]]:
            cur["status"] = item["status"]
            cur["axis"] = item["axis"]
            cur["weight"] = item["weight"]
            cur["note"] = item["note"]
        elif SEVERITY[item["status"]] == SEVERITY[cur["status"]]:
            winner = tie_evidence(cur, item)
            cur["axis"] = winner["axis"]
            cur["weight"] = winner["weight"]
            cur["note"] = winner["note"]
        if item["source"] == "independent" or cur["source"] == "independent":
            cur["source"] = "independent"
        if DISSENT[item["dissent"]] > DISSENT[cur["dissent"]]:
            cur["dissent"] = item["dissent"]
        cur["resolved"] = cur["resolved"] and item["resolved"]
    return list(merged.values())


def contribution(item):
    return {
        "ready": item["weight"],
        "watch": 0,
        "gap": -item["weight"],
        "blocked": -2 * item["weight"],
    }[item["status"]]


def reconcile(rec, prior, policy):
    by_id = {}
    closed_ids = set()
    for c in prior.get("open_commitments", []):
        by_id[c["id"]] = dict(c)
    for c in prior.get("closed_commitments", []):
        by_id[c["id"]] = dict(c)
        closed_ids.add(c["id"])
    for c in rec["commitments"]:
        by_id[c["id"]] = dict(c)
        if c["closed"]:
            closed_ids.add(c["id"])
    open_items = []
    closed_items = []
    overdue = False
    margin = policy.get("commitment_due_margin_days", 0)
    for c in by_id.values():
        if c["closed"] or c["id"] in closed_ids:
            c = dict(c)
            c["closed"] = True
            closed_items.append(c)
        else:
            open_items.append(c)
            if c["due_day"] + margin < rec["mission_days"]:
                overdue = True
    open_items.sort(key=lambda x: x["id"])
    closed_items.sort(key=lambda x: x["id"])
    return open_items, closed_items, overdue


def expected_board(record_dir, policy_path, prior_state=None):
    rec = read_record(record_dir)
    policy = json.loads(Path(policy_path).read_text())
    prior = prior_state or {
        "case_id": rec["case_id"],
        "run_count": 0,
        "open_commitments": [],
        "closed_commitments": [],
        "last_decision": "",
    }
    merged = merge_evidence(rec["evidence"])
    axis = {}
    critical = 0
    major = 0
    for item in merged:
        axis[item["axis"]] = axis.get(item["axis"], 0) + contribution(item)
        critical += int((not item["resolved"]) and item["dissent"] == "critical")
        major += int((not item["resolved"]) and item["dissent"] == "major")
    open_items, closed_items, overdue = reconcile(rec, prior, policy)
    open_ids = sorted(c["id"] for c in open_items)
    closed_ids = sorted(c["id"] for c in closed_items)
    prior_open = sorted(c["id"] for c in prior.get("open_commitments", []))
    stagnation = 8 if prior.get("run_count", 0) >= 1 and open_ids == prior_open else 0
    delegated = rec["emergency_authority"]["status"] == "delegated"
    decision = "AUTHORIZE"
    if (not delegated) or any(axis.get(k, 0) < v for k, v in policy["axis_floors"].items()) or (
        policy.get("critical_dissent_stops") and critical
    ):
        decision = "POSTPONE"
    elif policy.get("major_dissent_conditional") and major:
        decision = "CONDITIONAL_AUTHORIZE"
    elif open_ids or overdue:
        decision = "CONDITIONAL_AUTHORIZE"
    index = 50 + sum(axis.values()) * 4 - critical * 18 - major * 7
    if not delegated:
        index -= 25
    index -= stagnation
    index = max(0, min(100, index))
    return {
        "case_id": rec["case_id"],
        "decision": decision,
        "axis_scores": axis,
        "critical": critical,
        "major": major,
        "open_ids": open_ids,
        "closed_ids": closed_ids,
        "resilience_index": index,
        "resilience_label": resilience_label(index),
        "stagnation_penalty": stagnation,
        "overdue_open": overdue,
        "run_count": prior.get("run_count", 0) + 1,
        "technical_certification": rec["technical_certification"],
        "authority_status": rec["emergency_authority"]["status"],
        "merged": merged,
    }


def assert_surfaces_agree(proc, out_dir, expected):
    det, rows, memo, state, journal = artifacts(out_dir)
    assert det["case_id"] == expected["case_id"]
    assert det["decision"] == expected["decision"]
    assert det["axis_scores"] == expected["axis_scores"]
    assert det["unresolved_critical_dissent"] == expected["critical"]
    assert det["unresolved_major_dissent"] == expected["major"]
    assert det["resilience_index"] == expected["resilience_index"]
    assert det["stagnation_penalty"] == expected["stagnation_penalty"]
    assert det["overdue_open"] == expected["overdue_open"]
    assert f"case={expected['case_id']}" in proc.stdout
    assert f"decision={expected['decision']}" in proc.stdout
    assert f"resilience_index={expected['resilience_index']}" in proc.stdout
    assert rows[-1]["row_id"] == "TOTAL"
    assert rows[-1]["case_id"] == det["case_id"]
    assert rows[-1]["decision"] == det["decision"]
    assert int(rows[-1]["resilience_index"]) == det["resilience_index"]
    assert f"Case {expected['case_id']} readiness determination: {expected['decision']}." in memo
    assert (
        f"Resilience index: {expected['resilience_index']} ({expected['resilience_label']})."
        in memo
    )
    assert expected["case_id"] in state
    case_state = state[expected["case_id"]]
    assert case_state["last_decision"] == expected["decision"]
    assert case_state["run_count"] == expected["run_count"]
    assert sorted(det["open_commitment_ids"]) == expected["open_ids"]
    assert sorted(det["closed_commitment_ids"]) == expected["closed_ids"]
    assert sorted(det["open_commitment_ids"]) == sorted(
        c["id"] for c in case_state["open_commitments"]
    )
    assert sorted(det["closed_commitment_ids"]) == sorted(
        c["id"] for c in case_state["closed_commitments"]
    )
    assert journal, "review journal must contain at least one line"
    last = [j for j in journal if j["case_id"] == expected["case_id"]][-1]
    assert last["decision"] == expected["decision"]
    assert last["resilience_index"] == expected["resilience_index"]
    assert last["run_count"] == expected["run_count"]
    assert last["stagnation_penalty"] == expected["stagnation_penalty"]
    assert last["overdue_open"] == expected["overdue_open"]
    assert sorted(last["open_commitment_ids"]) == expected["open_ids"]
    assert_memo_contract(memo, expected["decision"])
    return det, rows, memo, state, journal


def copy_record(src, dst):
    shutil.copytree(src, dst)
    return dst


def read_record(path):
    return json.loads((path / "record.json").read_text())


def write_record(path, data):
    (path / "record.json").write_text(json.dumps(data, indent=2) + "\n")


def test_coupled_postponement_merge_state_score_and_journal(tmp_path):
    """Critical dissent postponement agrees across artifacts, journal, and shared state."""
    shared = tmp_path / "shared.json"
    proc, out_dir = run_review(
        ROOT / "data" / "orbital_alpha", tmp_path, state_path=shared, reset=True, out_name="alpha1"
    )
    expected = expected_board(ROOT / "data" / "orbital_alpha", POLICY)
    det, _rows, _memo, state, journal = assert_surfaces_agree(proc, out_dir, expected)
    assert expected["decision"] != "AUTHORIZE"
    assert expected["critical"] > 0
    assert det["technical_certification"].startswith("flight systems certified complete")
    assert det["emergency_authority_status"] == "delegated"
    assert state["ORBITAL-ALPHA"]["run_count"] == 1
    assert len(journal) == 1


def test_cross_case_state_isolation_and_authorize_path(tmp_path):
    """Shared state keeps independent histories; authorize path stays unpoisoned."""
    shared = tmp_path / "shared.json"
    run_review(ROOT / "data" / "orbital_alpha", tmp_path, state_path=shared, reset=True, out_name="a")
    proc, out_dir = run_review(
        ROOT / "data" / "orbital_beta", tmp_path, state_path=shared, out_name="b"
    )
    expected = expected_board(ROOT / "data" / "orbital_beta", POLICY)
    det, _rows, _memo, state, _journal = assert_surfaces_agree(proc, out_dir, expected)
    assert det["open_commitment_ids"] == []
    assert det["closed_commitment_ids"] == ["C-PSY-1"]
    assert sorted(state) == ["ORBITAL-ALPHA", "ORBITAL-BETA"]
    assert state["ORBITAL-ALPHA"]["open_commitments"]
    assert state["ORBITAL-BETA"]["open_commitments"] == []


def test_stagnation_penalty_on_repeated_open_set(tmp_path):
    """Second review with unchanged open commitments applies stagnation and advances run_count."""
    shared = tmp_path / "shared.json"
    out = tmp_path / "repeat"
    out.mkdir()
    run_review(
        ROOT / "data" / "orbital_alpha",
        tmp_path,
        state_path=shared,
        reset=True,
        out_name="repeat",
    )
    prior = json.loads(shared.read_text())["ORBITAL-ALPHA"]
    proc, out_dir = run_review(
        ROOT / "data" / "orbital_alpha",
        tmp_path,
        state_path=shared,
        out_name="repeat",
    )
    expected = expected_board(ROOT / "data" / "orbital_alpha", POLICY, prior_state=prior)
    det, _rows, _memo, state, journal = assert_surfaces_agree(proc, out_dir, expected)
    assert expected["stagnation_penalty"] > 0
    assert expected["run_count"] > 1
    assert det["resilience_index"] == expected["resilience_index"]
    assert state["ORBITAL-ALPHA"]["run_count"] == expected["run_count"]
    assert len([j for j in journal if j["case_id"] == "ORBITAL-ALPHA"]) == expected["run_count"]


def test_duplicate_evidence_order_independence_with_overdue_commitment(tmp_path):
    """Duplicate merge is order-independent and overdue opens force conditional when not postponed."""
    case_a = copy_record(ROOT / "data" / "orbital_beta", tmp_path / "case_a")
    case_b = copy_record(ROOT / "data" / "orbital_beta", tmp_path / "case_b")
    base = read_record(case_a)
    duplicate_ready = {
        "id": "crew-psych",
        "axis": "crew_support",
        "status": "ready",
        "weight": 2,
        "source": "internal",
        "dissent": "none",
        "resolved": True,
        "note": "internal closure claim",
    }
    duplicate_gap = {
        "id": "crew-psych",
        "axis": "crew_support",
        "status": "gap",
        "weight": 2,
        "source": "independent",
        "dissent": "major",
        "resolved": False,
        "note": "independent reviewer keeps crew support open",
    }
    base["case_id"] = "ORBITAL-MERGE-A"
    base["evidence"] = [duplicate_ready, duplicate_gap] + [
        e for e in base["evidence"] if e["id"] != "crew-psych"
    ]
    base["commitments"] = [
        {
            "id": "C-MERGE-1",
            "axis": "crew_support",
            "evidence_id": "crew-psych",
            "due_day": 9,
            "closed": False,
        }
    ]
    write_record(case_a, base)
    other = json.loads(json.dumps(base))
    other["case_id"] = "ORBITAL-MERGE-B"
    other["evidence"] = [duplicate_gap, duplicate_ready] + [
        e for e in base["evidence"] if e["id"] != "crew-psych"
    ]
    write_record(case_b, other)
    det_a, rows_a, _m_a, _s_a, _j_a = assert_surfaces_agree(
        *run_review(case_a, tmp_path, reset=True, out_name="ma"),
        expected_board(case_a, POLICY),
    )
    det_b, rows_b, _m_b, _s_b, _j_b = assert_surfaces_agree(
        *run_review(case_b, tmp_path, reset=True, out_name="mb"),
        expected_board(case_b, POLICY),
    )
    assert det_a["decision"] == det_b["decision"]
    assert det_a["unresolved_major_dissent"] == det_b["unresolved_major_dissent"] == 1
    crew_a = [r for r in rows_a if r["row_id"] == "crew-psych"][0]
    crew_b = [r for r in rows_b if r["row_id"] == "crew-psych"][0]
    assert crew_a["status"] == crew_b["status"] == "gap"
    assert crew_a["source"] == crew_b["source"] == "independent"
    assert crew_a["resolved"] == crew_b["resolved"] == "false"
    assert det_a["decision"] != "AUTHORIZE"


def test_sticky_closed_commitments_survive_reopened_record(tmp_path):
    """A commitment closed in prior case state stays closed even if a later record reopens it."""
    shared = tmp_path / "shared.json"
    run_review(ROOT / "data" / "orbital_beta", tmp_path, state_path=shared, reset=True, out_name="b1")
    case = copy_record(ROOT / "data" / "orbital_beta", tmp_path / "reopen")
    rec = read_record(case)
    rec["case_id"] = "ORBITAL-BETA"
    rec["commitments"] = [
        {
            "id": "C-PSY-1",
            "axis": "crew_support",
            "evidence_id": "crew-psych",
            "due_day": 14,
            "closed": False,
        }
    ]
    write_record(case, rec)
    prior = json.loads(shared.read_text())["ORBITAL-BETA"]
    proc, out_dir = run_review(case, tmp_path, state_path=shared, out_name="b2")
    expected = expected_board(case, POLICY, prior_state=prior)
    det, _rows, _memo, state, _journal = assert_surfaces_agree(proc, out_dir, expected)
    assert "C-PSY-1" in det["closed_commitment_ids"]
    assert "C-PSY-1" not in det["open_commitment_ids"]
    assert state["ORBITAL-BETA"]["run_count"] == 2


def test_policy_mutation_and_held_out_record(tmp_path):
    """Policy floors and a held-out mutated record both drive governance without altering certification text."""
    policy = json.loads(POLICY.read_text())
    policy["axis_floors"]["safety"] = 4
    policy_path = tmp_path / "strict_policy.json"
    policy_path.write_text(json.dumps(policy, indent=2) + "\n")
    proc, out_dir = run_review(
        ROOT / "data" / "orbital_beta",
        tmp_path,
        policy_path=policy_path,
        reset=True,
        out_name="pol",
    )
    expected = expected_board(ROOT / "data" / "orbital_beta", policy_path)
    det, _rows, memo, _state, _journal = assert_surfaces_agree(proc, out_dir, expected)
    assert expected["decision"] != "AUTHORIZE"
    assert det["axis_scores"]["safety"] < policy["axis_floors"]["safety"]
    assert det["technical_certification"] == "flight systems certified complete by engineering record FCR-82"
    assert_memo_contract(memo, expected["decision"])

    held = copy_record(ROOT / "data" / "orbital_beta", tmp_path / "held")
    rec = read_record(held)
    rec["case_id"] = "ORBITAL-HELD"
    for item in rec["evidence"]:
        if item["id"] == "ops-sim":
            item["weight"] = 4
        if item["id"] == "safety-panel":
            item["status"] = "watch"
            item["weight"] = 1
    write_record(held, rec)
    proc2, out2 = run_review(held, tmp_path, reset=True, out_name="held")
    expected2 = expected_board(held, POLICY)
    assert_surfaces_agree(proc2, out2, expected2)


def test_non_delegated_authority_rejects_before_any_publication(tmp_path):
    """Non-delegated emergency authority exits before public artifacts or journal lines appear."""
    case_dir = copy_record(ROOT / "data" / "orbital_beta", tmp_path / "invalid_authority")
    rec = read_record(case_dir)
    rec["case_id"] = "ORBITAL-INVALID"
    rec["emergency_authority"]["status"] = "documented"
    write_record(case_dir, rec)
    out_dir = tmp_path / "bad_out"
    out_dir.mkdir()
    proc, _ = run_review(case_dir, tmp_path, reset=True, expect_ok=False, out_name="bad_out")
    err = proc.stderr.lower()
    assert "emergency" in err and "authority" in err
    assert not (out_dir / "determination.json").exists()
    assert not list(out_dir.glob("*.jsonl")) or not any(
        p.read_text().strip() for p in out_dir.glob("*.jsonl")
    )


def test_delegated_empty_decision_document_rejects_before_publication(tmp_path):
    """Delegated authority with an empty decision document must reject before publication."""
    case_dir = copy_record(ROOT / "data" / "orbital_beta", tmp_path / "empty_decision_doc")
    rec = read_record(case_dir)
    rec["case_id"] = "ORBITAL-EMPTY-DOC"
    rec["emergency_authority"]["status"] = "delegated"
    rec["emergency_authority"]["decision_doc"] = ""
    write_record(case_dir, rec)
    out_dir = tmp_path / "empty_doc_out"
    out_dir.mkdir()
    proc, _ = run_review(case_dir, tmp_path, reset=True, expect_ok=False, out_name="empty_doc_out")
    err = proc.stderr.lower()
    assert "emergency" in err and "authority" in err
    assert not (out_dir / "determination.json").exists()


def test_equal_severity_duplicate_merge_uses_deterministic_tie_rule(tmp_path):
    """Equal-severity duplicates pick axis, weight, and note by the published tie rule."""
    case_a = copy_record(ROOT / "data" / "orbital_beta", tmp_path / "tie_a")
    case_b = copy_record(ROOT / "data" / "orbital_beta", tmp_path / "tie_b")
    base = read_record(case_a)
    dup_alpha = {
        "id": "crew-psych",
        "axis": "crew_support",
        "status": "gap",
        "weight": 5,
        "source": "internal",
        "dissent": "none",
        "resolved": True,
        "note": "alpha note",
    }
    dup_beta = {
        "id": "crew-psych",
        "axis": "crew_support",
        "status": "gap",
        "weight": 2,
        "source": "internal",
        "dissent": "none",
        "resolved": True,
        "note": "beta note",
    }
    base["case_id"] = "ORBITAL-TIE-A"
    base["evidence"] = [dup_alpha, dup_beta] + [
        e for e in base["evidence"] if e["id"] != "crew-psych"
    ]
    write_record(case_a, base)
    other = json.loads(json.dumps(base))
    other["case_id"] = "ORBITAL-TIE-B"
    other["evidence"] = [dup_beta, dup_alpha] + [
        e for e in base["evidence"] if e["id"] != "crew-psych"
    ]
    write_record(case_b, other)
    _proc_a, out_a = run_review(case_a, tmp_path, reset=True, out_name="tie_a")
    _proc_b, out_b = run_review(case_b, tmp_path, reset=True, out_name="tie_b")
    rows_a = list(csv.DictReader((out_a / "evidence_matrix.csv").open()))
    rows_b = list(csv.DictReader((out_b / "evidence_matrix.csv").open()))
    crew_a = [r for r in rows_a if r["row_id"] == "crew-psych"][0]
    crew_b = [r for r in rows_b if r["row_id"] == "crew-psych"][0]
    assert crew_a["status"] == crew_b["status"] == "gap"
    assert int(crew_a["score"]) == int(crew_b["score"]) == -5


def test_resilience_label_thresholds_in_memo(tmp_path):
    """Memo reports strong, guarded, or fragile labels at the published index thresholds."""
    proc, out_dir = run_review(
        ROOT / "data" / "orbital_beta", tmp_path, reset=True, out_name="label_beta"
    )
    expected = expected_board(ROOT / "data" / "orbital_beta", POLICY)
    _det, _rows, memo, _state, _journal = assert_surfaces_agree(proc, out_dir, expected)
    label = expected["resilience_label"]
    assert label in {"strong", "guarded", "fragile"}
    assert f"Resilience index: {expected['resilience_index']} ({label})." in memo
    if expected["resilience_index"] >= 82:
        assert label == "strong"
    elif expected["resilience_index"] >= 62:
        assert label == "guarded"
    else:
        assert label == "fragile"

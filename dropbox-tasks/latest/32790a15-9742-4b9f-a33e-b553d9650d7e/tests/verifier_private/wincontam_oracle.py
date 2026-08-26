"""Independent reference oracle for wincontam bulletins."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

MANIFESTS = (
    "conversation_sessions.json",
    "prompt_turn_log.json",
    "retrieval_injections.json",
    "tool_execution_outputs.json",
    "system_instruction_versions.json",
    "model_output_failures.json",
    "contamination_policy.json",
    "session_order_timeline.json",
)


def parse_ts(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def last_wins(rows: list[dict], key: str) -> list[dict]:
    seen: dict[str, dict] = {}
    for row in rows:
        seen[str(row[key])] = dict(row)
    return list(seen.values())


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def corpus_stamp(data_dir: Path) -> str:
    h = hashlib.sha256()
    for name in MANIFESTS:
        payload = load_json(data_dir / name)
        compact = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        h.update(compact.encode())
    return h.hexdigest()


def read_corpus(data_dir: Path) -> dict:
    sessions = last_wins(load_json(data_dir / "conversation_sessions.json")["sessions"], "session_id")
    turns = last_wins(load_json(data_dir / "prompt_turn_log.json")["turns"], "turn_id")
    retrievals = last_wins(load_json(data_dir / "retrieval_injections.json")["retrievals"], "retrieval_id")
    tools = last_wins(load_json(data_dir / "tool_execution_outputs.json")["tools"], "tool_id")
    versions = last_wins(load_json(data_dir / "system_instruction_versions.json")["versions"], "version_id")
    failures = last_wins(load_json(data_dir / "model_output_failures.json")["failures"], "failure_id")
    policy = load_json(data_dir / "contamination_policy.json")
    return {
        "sessions": sessions,
        "turns": turns,
        "retrievals": retrievals,
        "tools": tools,
        "versions": versions,
        "failures": failures,
        "policy": policy,
        "turn_by_id": {t["turn_id"]: t for t in turns},
    }


def eligible_turns(corpus: dict, cutoff: str) -> list[dict]:
    bound = parse_ts(cutoff)
    kept = [dict(t) for t in corpus["turns"] if parse_ts(t["completed_at"]) <= bound]
    kept.sort(key=lambda t: (parse_ts(t["completed_at"]), t["turn_id"]))
    return kept


def round_score(value: float, precision: int):
    rounded = round(value, precision)
    if abs(rounded - int(rounded)) < 1e-12:
        return int(rounded)
    return rounded


def attribute_failure(failure: dict, corpus: dict, cutoff: str) -> tuple[str, str, str, str]:
    turn = corpus["turn_by_id"][failure["turn_id"]]
    fail_ts = parse_ts(turn["completed_at"])
    bound = parse_ts(cutoff)
    session_id = failure["session_id"]
    threshold = int(corpus["policy"].get("repeat_fact_threshold", 2))

    active_versions = [
        v
        for v in corpus["versions"]
        if parse_ts(v["effective_from"]) <= fail_ts and parse_ts(v["effective_from"]) <= bound
    ]
    active_versions.sort(key=lambda v: (parse_ts(v["effective_from"]), v["version_id"]))
    for later in active_versions:
        conflicts = set(later.get("conflicts_with") or [])
        for earlier in active_versions:
            if earlier["version_id"] == later["version_id"]:
                continue
            if parse_ts(earlier["effective_from"]) < parse_ts(later["effective_from"]) and earlier["version_id"] in conflicts:
                return "instruction_conflict", "none", "none", later["version_id"]

    cutoff_retrievals = [
        r
        for r in corpus["retrievals"]
        if r["session_id"] == session_id and parse_ts(r["retrieved_at"]) <= bound
    ]
    session_retrievals = [r for r in cutoff_retrievals if parse_ts(r["retrieved_at"]) <= fail_ts]
    by_query: dict[str, list[dict]] = {}
    for row in cutoff_retrievals:
        by_query.setdefault(row["query_key"], []).append(row)
    for query_key, rows in sorted(by_query.items()):
        earlier_rows = sorted(
            [r for r in rows if parse_ts(r["retrieved_at"]) <= fail_ts],
            key=lambda r: (parse_ts(r["retrieved_at"]), r["retrieval_id"]),
        )
        for earlier in earlier_rows:
            earlier_ts = parse_ts(earlier["retrieved_at"])
            for later in rows:
                later_ts = parse_ts(later["retrieved_at"])
                if later_ts > earlier_ts and later["content_hash"] != earlier["content_hash"]:
                    return "stale_retrieval", query_key, "none", "none"

    session_tools = [
        t
        for t in corpus["tools"]
        if t["session_id"] == session_id
        and parse_ts(t["executed_at"]) <= fail_ts
        and parse_ts(t["executed_at"]) <= bound
    ]
    if session_tools:
        tool = sorted(session_tools, key=lambda t: (parse_ts(t["executed_at"]), t["tool_id"]))[0]
        return "tool_artifact_bleed", "none", tool["tool_id"], "none"

    hash_counts: dict[str, int] = {}
    for row in session_retrievals:
        hash_counts[row["content_hash"]] = hash_counts.get(row["content_hash"], 0) + 1
    for _content_hash, count in sorted(hash_counts.items()):
        if count >= threshold:
            return "repeated_fact_injection", "none", "none", "none"

    return "residual_contam", "none", "none", "none"


def build_evidence(session_id, turn_id, failure_id, cause, query_key, tool_id, instruction_id):
    tokens = [
        f"session:{session_id}",
        f"turn:{turn_id}",
        f"failure:{failure_id}",
        f"cause:{cause}",
        f"retrieval:{query_key}",
        f"tool:{tool_id}",
        f"instruction:{instruction_id}",
        "status:flagged",
    ]
    return sorted(tokens)


def attest_digest(cutoff: str, emitted_at: str, contaminated_failures: int) -> str:
    payload = {
        "contaminated_failures": contaminated_failures,
        "cutoff": cutoff,
        "emitted_at": emitted_at,
    }
    compact = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(compact.encode()).hexdigest()


def reference_bulletin(data_dir: Path, cutoff: str, emitted_at: str) -> dict:
    corpus = read_corpus(data_dir)
    precision = int(corpus["policy"].get("score_precision", 4))
    min_sev = float(corpus["policy"].get("min_severity_score", 0.75))
    turns = eligible_turns(corpus, cutoff)
    turn_ids = {t["turn_id"] for t in turns}
    failures = [
        f
        for f in corpus["failures"]
        if f["turn_id"] in turn_ids and parse_ts(f["observed_at"]) <= parse_ts(cutoff)
    ]
    failures.sort(key=lambda f: (f["session_id"], f["turn_id"], f["failure_id"]))

    rows = []
    for failure in failures:
        cause, query_key, tool_id, instruction_id = attribute_failure(failure, corpus, cutoff)
        rows.append(
            {
                "contam_id": f"contam_{failure['session_id']}_{failure['turn_id']}",
                "session_id": failure["session_id"],
                "turn_id": failure["turn_id"],
                "failure_id": failure["failure_id"],
                "attribution_primary": cause,
                "severity_score": None,
                "evidence": build_evidence(
                    failure["session_id"],
                    failure["turn_id"],
                    failure["failure_id"],
                    cause,
                    query_key,
                    tool_id,
                    instruction_id,
                ),
            }
        )

    assistant_by_session: dict[str, int] = {}
    for turn in turns:
        if turn.get("role") == "assistant":
            assistant_by_session[turn["session_id"]] = assistant_by_session.get(turn["session_id"], 0) + 1

    contam_by_session: dict[str, int] = {}
    for row in rows:
        contam_by_session[row["session_id"]] = contam_by_session.get(row["session_id"], 0) + 1

    scorecard = []
    session_scores = {}
    for session_id in sorted(assistant_by_session):
        eligible = assistant_by_session[session_id]
        contaminated = contam_by_session.get(session_id, 0)
        score = round_score(1.0 - (contaminated / eligible), precision)
        session_scores[session_id] = score
        scorecard.append(
            {
                "session_id": session_id,
                "eligible_assistant_turns": eligible,
                "contaminated_failures": contaminated,
                "severity_score": score,
                "needs_review": float(score) + 1e-12 < min_sev,
            }
        )

    for row in rows:
        row["severity_score"] = session_scores[row["session_id"]]

    rows.sort(key=lambda r: (r["session_id"], r["turn_id"], r["contam_id"]))
    flagged = sum(1 for s in scorecard if s["needs_review"])
    evaluated_sessions = {t["session_id"] for t in turns}

    return {
        "emitted_at": emitted_at,
        "cutoff": cutoff,
        "contam_summary": {
            "sessions_in_corpus": len(corpus["sessions"]),
            "failures_analyzed": len(rows),
            "contaminated_failures": len(rows),
            "sessions_flagged": flagged,
        },
        "contam_rows": rows,
        "session_scorecard": scorecard,
        "coverage": {
            "coverage_total": len(corpus["sessions"]),
            "coverage_evaluated": len(evaluated_sessions),
        },
        "attestation": {"attest_digest": attest_digest(cutoff, emitted_at, len(rows))},
    }

use anyhow::Result;
use chrono::{DateTime, Utc};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

use crate::causechain::attribute_failure;
use crate::ctxhold::dedupe::dedupe_last_wins;
use crate::ctxhold::{read_json, sort_value};
use crate::featmetrics::{needs_review, round_score};

fn parse_ts(raw: &str) -> Result<DateTime<Utc>> {
    let normalized = if raw.ends_with('Z') {
        raw.replace('Z', "+00:00")
    } else {
        raw.to_string()
    };
    Ok(DateTime::parse_from_rfc3339(&normalized)?.with_timezone(&Utc))
}

fn load_corpus(data: &Path) -> Result<Value> {
    let sessions = dedupe_last_wins(
        read_json(&data.join("conversation_sessions.json"))?
            .get("sessions")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default()
            .as_slice(),
        "session_id",
    );
    let turns = dedupe_last_wins(
        read_json(&data.join("prompt_turn_log.json"))?
            .get("turns")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default()
            .as_slice(),
        "turn_id",
    );
    let retrievals = dedupe_last_wins(
        read_json(&data.join("retrieval_injections.json"))?
            .get("retrievals")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default()
            .as_slice(),
        "retrieval_id",
    );
    let tools = dedupe_last_wins(
        read_json(&data.join("tool_execution_outputs.json"))?
            .get("tools")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default()
            .as_slice(),
        "tool_id",
    );
    let versions = dedupe_last_wins(
        read_json(&data.join("system_instruction_versions.json"))?
            .get("versions")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default()
            .as_slice(),
        "version_id",
    );
    let failures = dedupe_last_wins(
        read_json(&data.join("model_output_failures.json"))?
            .get("failures")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default()
            .as_slice(),
        "failure_id",
    );
    let policy = read_json(&data.join("contamination_policy.json"))?;
    Ok(json!({
        "sessions": sessions,
        "turns": turns,
        "retrievals": retrievals,
        "tools": tools,
        "versions": versions,
        "failures": failures,
        "policy": policy,
    }))
}

fn attest_digest(cutoff: &str, emitted_at: &str, contaminated: usize) -> String {
    let payload = json!({
        "cutoff": cutoff,
        "contaminated_failures": contaminated,
        "emitted_at": emitted_at,
    });
    let compact = serde_json::to_string(&sort_value(&payload)).unwrap();
    let mut hasher = Sha256::new();
    hasher.update(compact.as_bytes());
    hex::encode(hasher.finalize())
}

pub fn build_report(data: &Path, cutoff: &str, emitted_at: &str) -> Result<Value> {
    let corpus = load_corpus(data)?;
    let bound = parse_ts(cutoff)?;
    let precision = corpus
        .get("policy")
        .and_then(|p| p.get("score_precision"))
        .and_then(|v| v.as_u64())
        .unwrap_or(4) as i32;
    let min_sev = corpus
        .get("policy")
        .and_then(|p| p.get("min_severity_score"))
        .and_then(|v| v.as_f64())
        .unwrap_or(0.75);

    let mut turns: Vec<Value> = corpus
        .get("turns")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter(|t| {
            t.get("completed_at")
                .and_then(|v| v.as_str())
                .and_then(|s| parse_ts(s).ok())
                .map(|ts| ts < bound)
                .unwrap_or(false)
        })
        .collect();
    turns.sort_by(|a, b| {
        let ta = parse_ts(a.get("completed_at").and_then(|v| v.as_str()).unwrap_or("")).unwrap();
        let tb = parse_ts(b.get("completed_at").and_then(|v| v.as_str()).unwrap_or("")).unwrap();
        let ida = a.get("turn_id").and_then(|v| v.as_str()).unwrap_or("");
        let idb = b.get("turn_id").and_then(|v| v.as_str()).unwrap_or("");
        ta.cmp(&tb).then(ida.cmp(idb))
    });
    let turn_ids: BTreeSet<String> = turns
        .iter()
        .filter_map(|t| t.get("turn_id").and_then(|v| v.as_str()).map(|s| s.to_string()))
        .collect();

    let mut failures: Vec<Value> = corpus
        .get("failures")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter(|f| {
            let tid = f.get("turn_id").and_then(|v| v.as_str()).unwrap_or("");
            let obs = f
                .get("observed_at")
                .and_then(|v| v.as_str())
                .and_then(|s| parse_ts(s).ok());
            turn_ids.contains(tid) && obs.map(|ts| ts < bound).unwrap_or(false)
        })
        .collect();
    failures.sort_by(|a, b| {
        let sa = a.get("session_id").and_then(|v| v.as_str()).unwrap_or("");
        let sb = b.get("session_id").and_then(|v| v.as_str()).unwrap_or("");
        let ta = a.get("turn_id").and_then(|v| v.as_str()).unwrap_or("");
        let tb = b.get("turn_id").and_then(|v| v.as_str()).unwrap_or("");
        let fa = a.get("failure_id").and_then(|v| v.as_str()).unwrap_or("");
        let fb = b.get("failure_id").and_then(|v| v.as_str()).unwrap_or("");
        sa.cmp(sb).then(ta.cmp(tb)).then(fa.cmp(fb))
    });

    let mut assistant_by_session: BTreeMap<String, usize> = BTreeMap::new();
    for turn in &turns {
        if turn.get("role").and_then(|v| v.as_str()) == Some("assistant") {
            let sid = turn
                .get("session_id")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            *assistant_by_session.entry(sid).or_insert(0) += 1;
        }
    }

    let mut contam_by_session: BTreeMap<String, usize> = BTreeMap::new();
    let mut rows = Vec::new();
    for failure in &failures {
        let (cause, query, tool, instruction) = attribute_failure(failure, &corpus, cutoff)?;
        let session_id = failure
            .get("session_id")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let turn_id = failure
            .get("turn_id")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let failure_id = failure
            .get("failure_id")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        *contam_by_session.entry(session_id.clone()).or_insert(0) += 1;
        let mut evidence = vec![
            format!("session:{session_id}"),
            format!("turn:{turn_id}"),
            format!("failure:{failure_id}"),
            format!("cause:{cause}"),
            format!("retrieval:{query}"),
            format!("tool:{tool}"),
            format!("instruction:{instruction}"),
            "status:flagged".to_string(),
        ];
        evidence.sort();
        rows.push(json!({
            "contam_id": format!("contam_{session_id}_{turn_id}"),
            "session_id": session_id,
            "turn_id": turn_id,
            "failure_id": failure_id,
            "attribution_primary": cause,
            "severity_score": Value::Null,
            "evidence": evidence,
        }));
    }

    let mut scorecard = Vec::new();
    let mut session_scores: BTreeMap<String, Value> = BTreeMap::new();
    for (session_id, eligible) in &assistant_by_session {
        let contaminated = *contam_by_session.get(session_id).unwrap_or(&0);
        let score = round_score(1.0 - (contaminated as f64 / *eligible as f64), precision);
        session_scores.insert(session_id.clone(), score.clone());
        scorecard.push(json!({
            "session_id": session_id,
            "eligible_assistant_turns": eligible,
            "contaminated_failures": contaminated,
            "severity_score": score.clone(),
            "needs_review": needs_review(&score, min_sev),
        }));
    }

    for row in &mut rows {
        let sid = row.get("session_id").and_then(|v| v.as_str()).unwrap_or("");
        if let Some(score) = session_scores.get(sid) {
            row.as_object_mut()
                .unwrap()
                .insert("severity_score".to_string(), score.clone());
        }
    }
    rows.sort_by(|a, b| {
        let sa = a.get("session_id").and_then(|v| v.as_str()).unwrap_or("");
        let sb = b.get("session_id").and_then(|v| v.as_str()).unwrap_or("");
        let ta = a.get("turn_id").and_then(|v| v.as_str()).unwrap_or("");
        let tb = b.get("turn_id").and_then(|v| v.as_str()).unwrap_or("");
        let ca = a.get("contam_id").and_then(|v| v.as_str()).unwrap_or("");
        let cb = b.get("contam_id").and_then(|v| v.as_str()).unwrap_or("");
        sa.cmp(sb).then(ta.cmp(tb)).then(ca.cmp(cb))
    });

    let flagged = scorecard
        .iter()
        .filter(|s| s.get("needs_review").and_then(|v| v.as_bool()).unwrap_or(false))
        .count();
    let evaluated: BTreeSet<String> = turns
        .iter()
        .filter_map(|t| t.get("session_id").and_then(|v| v.as_str()).map(|s| s.to_string()))
        .collect();
    let sessions_len = corpus
        .get("sessions")
        .and_then(|v| v.as_array())
        .map(|a| a.len())
        .unwrap_or(0);

    Ok(json!({
        "emitted_at": emitted_at,
        "cutoff": cutoff,
        "contam_summary": {
            "sessions_in_corpus": sessions_len,
            "failures_analyzed": rows.len(),
            "contaminated_failures": rows.len(),
            "sessions_flagged": flagged,
        },
        "contam_rows": rows,
        "session_scorecard": scorecard,
        "coverage": {
            "coverage_total": sessions_len,
            "coverage_evaluated": evaluated.len(),
        },
        "attestation": {
            "attest_digest": attest_digest(cutoff, emitted_at, rows.len()),
        },
    }))
}

pub mod report {
    #[allow(unused_imports)]
    pub use super::build_report;
}

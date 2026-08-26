use anyhow::Result;
use chrono::{DateTime, Utc};
use serde_json::Value;

fn parse_ts(raw: &str) -> Result<DateTime<Utc>> {
    let normalized = if raw.ends_with('Z') {
        raw.replace('Z', "+00:00")
    } else {
        raw.to_string()
    };
    Ok(DateTime::parse_from_rfc3339(&normalized)?.with_timezone(&Utc))
}

pub fn attribute_failure(
    failure: &Value,
    corpus: &Value,
    cutoff: &str,
) -> Result<(String, String, String, String)> {
    let turn_id = failure.get("turn_id").and_then(|v| v.as_str()).unwrap_or("");
    let session_id = failure
        .get("session_id")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let turns = corpus.get("turns").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let turn = turns
        .iter()
        .find(|t| t.get("turn_id").and_then(|v| v.as_str()) == Some(turn_id))
        .cloned()
        .unwrap_or(Value::Null);
    let fail_ts = parse_ts(turn.get("completed_at").and_then(|v| v.as_str()).unwrap_or(""))?;
    let cutoff = parse_ts(cutoff)?;
    let threshold = corpus
        .get("policy")
        .and_then(|p| p.get("repeat_fact_threshold"))
        .and_then(|v| v.as_u64())
        .unwrap_or(2) as usize;

    let mut versions: Vec<Value> = corpus
        .get("versions")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter(|v| {
            v.get("effective_from")
                .and_then(|x| x.as_str())
                .and_then(|s| parse_ts(s).ok())
                .map(|ts| ts <= fail_ts && ts <= cutoff)
                .unwrap_or(false)
        })
        .collect();
    versions.sort_by(|a, b| {
        let ta = parse_ts(a.get("effective_from").and_then(|v| v.as_str()).unwrap_or("")).unwrap();
        let tb = parse_ts(b.get("effective_from").and_then(|v| v.as_str()).unwrap_or("")).unwrap();
        let ia = a.get("version_id").and_then(|v| v.as_str()).unwrap_or("");
        let ib = b.get("version_id").and_then(|v| v.as_str()).unwrap_or("");
        ta.cmp(&tb).then(ia.cmp(ib))
    });
    for later in &versions {
        let later_id = later.get("version_id").and_then(|v| v.as_str()).unwrap_or("");
        let later_ts = parse_ts(later.get("effective_from").and_then(|v| v.as_str()).unwrap_or(""))?;
        let conflicts = later
            .get("conflicts_with")
            .and_then(|v| v.as_array())
            .cloned()
            .unwrap_or_default();
        let conflict_set: Vec<String> = conflicts
            .iter()
            .filter_map(|v| v.as_str().map(|s| s.to_string()))
            .collect();
        for earlier in &versions {
            let earlier_id = earlier.get("version_id").and_then(|v| v.as_str()).unwrap_or("");
            if earlier_id == later_id {
                continue;
            }
            let earlier_ts =
                parse_ts(earlier.get("effective_from").and_then(|v| v.as_str()).unwrap_or(""))?;
            if earlier_ts < later_ts && conflict_set.iter().any(|c| c == earlier_id) {
                return Ok((
                    "instruction_conflict".into(),
                    "none".into(),
                    "none".into(),
                    later_id.to_string(),
                ));
            }
        }
    }

    let all_retrievals: Vec<Value> = corpus
        .get("retrievals")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter(|r| {
            r.get("session_id").and_then(|v| v.as_str()) == Some(session_id)
                && r.get("retrieved_at")
                    .and_then(|v| v.as_str())
                    .and_then(|s| parse_ts(s).ok())
                    .map(|ts| ts <= cutoff)
                    .unwrap_or(false)
        })
        .collect();
    let session_retrievals: Vec<Value> = all_retrievals
        .iter()
        .filter(|r| {
            r.get("retrieved_at")
                .and_then(|v| v.as_str())
                .and_then(|s| parse_ts(s).ok())
                .map(|ts| ts <= fail_ts)
                .unwrap_or(false)
        })
        .cloned()
        .collect();
    let mut by_query: std::collections::BTreeMap<String, Vec<Value>> =
        std::collections::BTreeMap::new();
    for row in &all_retrievals {
        let q = row
            .get("query_key")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        by_query.entry(q).or_default().push(row.clone());
    }
    for (query_key, rows) in by_query {
        let mut earlier_rows: Vec<&Value> = rows
            .iter()
            .filter(|r| {
                r.get("retrieved_at")
                    .and_then(|v| v.as_str())
                    .and_then(|s| parse_ts(s).ok())
                    .map(|ts| ts <= fail_ts)
                    .unwrap_or(false)
            })
            .collect();
        earlier_rows.sort_by(|a, b| {
            let ta = parse_ts(a.get("retrieved_at").and_then(|v| v.as_str()).unwrap_or("")).unwrap();
            let tb = parse_ts(b.get("retrieved_at").and_then(|v| v.as_str()).unwrap_or("")).unwrap();
            let ia = a.get("retrieval_id").and_then(|v| v.as_str()).unwrap_or("");
            let ib = b.get("retrieval_id").and_then(|v| v.as_str()).unwrap_or("");
            ta.cmp(&tb).then(ia.cmp(ib))
        });
        for earlier in &earlier_rows {
            let earlier_ts =
                parse_ts(earlier.get("retrieved_at").and_then(|v| v.as_str()).unwrap_or(""))?;
            let earlier_hash = earlier
                .get("content_hash")
                .and_then(|v| v.as_str())
                .unwrap_or("");
            for later in &rows {
                let later_ts =
                    parse_ts(later.get("retrieved_at").and_then(|v| v.as_str()).unwrap_or(""))?;
                let later_hash = later
                    .get("content_hash")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                if later_ts > earlier_ts && later_hash != earlier_hash {
                    return Ok((
                        "stale_retrieval".into(),
                        query_key,
                        "none".into(),
                        "none".into(),
                    ));
                }
            }
        }
    }

    let mut session_tools: Vec<Value> = corpus
        .get("tools")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter(|t| {
            t.get("session_id").and_then(|v| v.as_str()) == Some(session_id)
                && t.get("executed_at")
                    .and_then(|v| v.as_str())
                    .and_then(|s| parse_ts(s).ok())
                    .map(|ts| ts <= fail_ts && ts <= cutoff)
                    .unwrap_or(false)
        })
        .collect();
    if !session_tools.is_empty() {
        session_tools.sort_by(|a, b| {
            let ta = parse_ts(a.get("executed_at").and_then(|v| v.as_str()).unwrap_or("")).unwrap();
            let tb = parse_ts(b.get("executed_at").and_then(|v| v.as_str()).unwrap_or("")).unwrap();
            let ia = a.get("tool_id").and_then(|v| v.as_str()).unwrap_or("");
            let ib = b.get("tool_id").and_then(|v| v.as_str()).unwrap_or("");
            ta.cmp(&tb).then(ia.cmp(ib))
        });
        let tool_id = session_tools[0]
            .get("tool_id")
            .and_then(|v| v.as_str())
            .unwrap_or("none")
            .to_string();
        return Ok((
            "tool_artifact_bleed".into(),
            "none".into(),
            tool_id,
            "none".into(),
        ));
    }

    let mut hash_counts: std::collections::BTreeMap<String, usize> =
        std::collections::BTreeMap::new();
    for row in &session_retrievals {
        if let Some(h) = row.get("content_hash").and_then(|v| v.as_str()) {
            *hash_counts.entry(h.to_string()).or_insert(0) += 1;
        }
    }
    for (_hash, count) in hash_counts {
        if count >= threshold {
            return Ok((
                "repeated_fact_injection".into(),
                "none".into(),
                "none".into(),
                "none".into(),
            ));
        }
    }

    Ok((
        "residual_contam".into(),
        "none".into(),
        "none".into(),
        "none".into(),
    ))
}

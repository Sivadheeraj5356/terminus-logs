//! Reference-measurement appraisal.

use std::collections::HashMap;

use crate::load::{Event, Policy};

#[derive(Debug, Clone)]
pub struct RuleResult {
    pub rule_id: String,
    pub rule_kind: String,
    pub matched_event_sequences: Vec<u32>,
    pub status: String,
    pub reason_or_null: Option<String>,
    pub failed: bool,
}

#[derive(Debug, Clone)]
pub struct AppraisalResult {
    pub rule_results: Vec<RuleResult>,
    /// seq -> (status, rule_id_or_null)
    pub event_policy_status: HashMap<u32, (String, Option<String>)>,
    pub matched_rule_count: u32,
    pub failed_rule_count: u32,
    pub reject_reason: Option<String>,
    pub order_failed: Option<(String, String)>,
}

pub fn appraise(policy: &Policy, events: &[Event]) -> AppraisalResult {
    let rules = &policy.measurement_rules;
    let mut ordered_rule_ids: Vec<String> = rules.keys().cloned().collect();
    ordered_rule_ids.sort();

    let mut selector_map: HashMap<(u32, String, String), String> = HashMap::new();
    for (rid, rule) in rules {
        selector_map.insert(
            (
                rule.pcr_index,
                rule.event_type.clone(),
                rule.component.clone(),
            ),
            rid.clone(),
        );
    }

    let mut matches: HashMap<String, Vec<Event>> =
        rules.keys().map(|rid| (rid.clone(), Vec::new())).collect();
    let mut event_status: HashMap<u32, (String, Option<String>)> = HashMap::new();
    let mut unknown_seqs: Vec<u32> = Vec::new();

    let mut ordered_events: Vec<&Event> = events.iter().collect();
    ordered_events.sort_by_key(|e| e.event_seq);

    for ev in ordered_events {
        let sel = (
            ev.pcr_index,
            ev.event_type.clone(),
            ev.component.clone(),
        );
        if let Some(rid) = selector_map.get(&sel) {
            matches.get_mut(rid).unwrap().push(ev.clone());
            event_status.insert(ev.event_seq, ("matched".into(), Some(rid.clone())));
        } else {
            unknown_seqs.push(ev.event_seq);
            event_status.insert(ev.event_seq, ("pending_unknown".into(), None));
        }
    }

    let mut rule_results: Vec<RuleResult> = Vec::new();
    let mut reject_reason: Option<String> = None;
    let mut first_fail_done = false;

    for rid in &ordered_rule_ids {
        let rule = &rules[rid];
        let evs = &matches[rid];
        let mut seqs: Vec<u32> = evs.iter().map(|e| e.event_seq).collect();
        seqs.sort_unstable();
        let kind = rule.kind.as_str();
        let mut status = "matched".to_string();
        let mut reason: Option<String> = None;
        let mut failed = false;

        if kind == "forbidden" {
            if !evs.is_empty() {
                status = "forbidden_present".into();
                reason = Some("forbidden_event_present".into());
                failed = true;
                for e in evs {
                    event_status.insert(e.event_seq, ("rejected".into(), Some(rid.clone())));
                }
            }
        } else if kind == "required" {
            if evs.is_empty() {
                status = "missing".into();
                reason = Some("required_event_missing".into());
                failed = true;
            } else if evs.len() > 1 {
                status = "duplicate".into();
                reason = Some("multiple_matching_events".into());
                failed = true;
                for e in evs {
                    event_status.insert(e.event_seq, ("rejected".into(), Some(rid.clone())));
                }
            } else {
                let e = &evs[0];
                if !rule.allowed_versions.iter().any(|v| v == &e.version) {
                    status = "version_mismatch".into();
                    reason = Some("event_version_not_allowed".into());
                    failed = true;
                    event_status.insert(e.event_seq, ("rejected".into(), Some(rid.clone())));
                } else if !rule
                    .allowed_digests
                    .iter()
                    .any(|d| d == &e.measurement_digest)
                {
                    status = "digest_mismatch".into();
                    reason = Some("event_digest_not_allowed".into());
                    failed = true;
                    event_status.insert(e.event_seq, ("rejected".into(), Some(rid.clone())));
                } else {
                    status = "matched".into();
                    event_status.insert(e.event_seq, ("matched".into(), Some(rid.clone())));
                }
            }
        } else {
            // optional
            if evs.is_empty() {
                status = "absent_allowed".into();
            } else if evs.len() > 1 {
                status = "duplicate".into();
                reason = Some("multiple_matching_events".into());
                failed = true;
                for e in evs {
                    event_status.insert(e.event_seq, ("rejected".into(), Some(rid.clone())));
                }
            } else {
                let e = &evs[0];
                if !rule.allowed_versions.iter().any(|v| v == &e.version) {
                    status = "version_mismatch".into();
                    reason = Some("event_version_not_allowed".into());
                    failed = true;
                    event_status.insert(e.event_seq, ("rejected".into(), Some(rid.clone())));
                } else if !rule
                    .allowed_digests
                    .iter()
                    .any(|d| d == &e.measurement_digest)
                {
                    status = "digest_mismatch".into();
                    reason = Some("event_digest_not_allowed".into());
                    failed = true;
                    event_status.insert(e.event_seq, ("rejected".into(), Some(rid.clone())));
                } else {
                    status = "matched".into();
                    event_status.insert(e.event_seq, ("matched".into(), Some(rid.clone())));
                }
            }
        }

        rule_results.push(RuleResult {
            rule_id: rid.clone(),
            rule_kind: kind.to_string(),
            matched_event_sequences: seqs,
            status,
            reason_or_null: reason,
            failed,
        });
        if failed && !first_fail_done {
            reject_reason = Some("reference_measurement_mismatch".into());
            first_fail_done = true;
        }
    }

    // Unknown events
    if policy.unknown_event_mode == "reject" && !unknown_seqs.is_empty() && !first_fail_done {
        reject_reason = Some("reference_measurement_mismatch".into());
        for seq in &unknown_seqs {
            event_status.insert(*seq, ("rejected".into(), None));
        }
    } else {
        for seq in &unknown_seqs {
            let st = event_status
                .get(seq)
                .map(|(s, _)| s.as_str())
                .unwrap_or("");
            if st == "pending_unknown" {
                if policy.unknown_event_mode == "allow" {
                    event_status.insert(*seq, ("allowed_unknown".into(), None));
                } else {
                    event_status.insert(*seq, ("rejected".into(), None));
                }
            }
        }
    }

    let mut order_failed: Option<(String, String)> = None;
    if reject_reason.is_none() {
        if policy.unknown_event_mode == "reject" && !unknown_seqs.is_empty() {
            reject_reason = Some("reference_measurement_mismatch".into());
        } else {
            let mut constraints = policy.order_constraints.clone();
            constraints.sort_by(|a, b| {
                (&a.before_rule_id, &a.after_rule_id)
                    .cmp(&(&b.before_rule_id, &b.after_rule_id))
            });
            for c in &constraints {
                let b_evs = &matches[&c.before_rule_id];
                let a_evs = &matches[&c.after_rule_id];
                if b_evs.len() == 1 && a_evs.len() == 1 {
                    if !(b_evs[0].event_seq < a_evs[0].event_seq) {
                        reject_reason = Some("event_order_violation".into());
                        order_failed =
                            Some((c.before_rule_id.clone(), c.after_rule_id.clone()));
                        break;
                    }
                }
            }
        }
    }

    let matched_rule_count = rule_results
        .iter()
        .filter(|r| r.status == "matched")
        .count() as u32;
    let failed_rule_count = rule_results.iter().filter(|r| r.failed).count() as u32;

    // Normalize pending_unknown leftovers
    let pending: Vec<u32> = event_status
        .iter()
        .filter(|(_, (st, _))| st == "pending_unknown")
        .map(|(seq, _)| *seq)
        .collect();
    for seq in pending {
        let st = if policy.unknown_event_mode == "allow" {
            "allowed_unknown"
        } else {
            "rejected"
        };
        event_status.insert(seq, (st.into(), None));
    }

    AppraisalResult {
        rule_results,
        event_policy_status: event_status,
        matched_rule_count,
        failed_rule_count,
        reject_reason,
        order_failed,
    }
}

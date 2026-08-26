use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use std::cmp::Ordering;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

fn s<'a>(v: &'a Value, key: &str) -> &'a str {
    v.get(key).and_then(Value::as_str).unwrap_or("")
}

fn i(v: &Value, key: &str) -> i64 {
    v.get(key).and_then(Value::as_i64).unwrap_or(0)
}

fn string_array(v: &Value, key: &str) -> Vec<String> {
    v.get(key)
        .and_then(Value::as_array)
        .map(|a| a.iter().filter_map(Value::as_str).map(str::to_string).collect())
        .unwrap_or_default()
}

fn read_json(path: PathBuf) -> Value {
    serde_json::from_str(&fs::read_to_string(path).expect("read json")).expect("parse json")
}

fn read_jsonl(path: PathBuf) -> Vec<Value> {
    fs::read_to_string(path)
        .unwrap_or_default()
        .lines()
        .filter(|line| !line.trim().is_empty())
        .map(|line| serde_json::from_str(line).expect("parse jsonl"))
        .collect()
}

fn canonical(fields: &[(&str, Value)]) -> Vec<u8> {
    let parts: Vec<String> = fields
        .iter()
        .map(|(k, v)| {
            format!(
                "{}:{}",
                serde_json::to_string(k).expect("key"),
                serde_json::to_string(v).expect("value")
            )
        })
        .collect();
    format!("{{{}}}", parts.join(",")).into_bytes()
}

fn att_payload(att: &Value) -> Vec<u8> {
    canonical(&[
        ("artifact_id", json!(s(att, "artifact_id"))),
        ("artifact_version", json!(s(att, "artifact_version"))),
        ("predicate", json!(s(att, "predicate"))),
        ("digest", json!(s(att, "digest"))),
        ("issued_at", json!(s(att, "issued_at"))),
        ("signer_id", json!(s(att, "signer_id"))),
        ("log_id", json!(s(att, "log_id"))),
        ("checkpoint_id", json!(s(att, "checkpoint_id"))),
    ])
}

fn checkpoint_payload(cp: &Value) -> Vec<u8> {
    canonical(&[
        ("checkpoint_id", json!(s(cp, "checkpoint_id"))),
        ("log_id", json!(s(cp, "log_id"))),
        ("tree_size", json!(i(cp, "tree_size"))),
        ("root_hash", json!(s(cp, "root_hash"))),
        ("signed_at", json!(s(cp, "signed_at"))),
    ])
}

fn sha256_hex(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    digest.iter().map(|b| format!("{:02x}", b)).collect()
}

fn signed_hex(secret: &str, payload: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(secret.as_bytes());
    h.update(b"\n");
    h.update(payload);
    h.finalize().iter().map(|b| format!("{:02x}", b)).collect()
}

fn hex_to_bytes(hex: &str) -> Option<Vec<u8>> {
    if hex.len() % 2 != 0 || !hex.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)) {
        return None;
    }
    let mut out = Vec::with_capacity(hex.len() / 2);
    for idx in (0..hex.len()).step_by(2) {
        out.push(u8::from_str_radix(&hex[idx..idx + 2], 16).ok()?);
    }
    Some(out)
}

fn inclusion_ok(att: &Value, inclusion: Option<&Value>, checkpoint: &Value) -> bool {
    let Some(inc) = inclusion else {
        return false;
    };
    let tree_size = i(checkpoint, "tree_size");
    let leaf_index = i(inc, "leaf_index");
    if leaf_index < 0 || leaf_index >= tree_size {
        return false;
    }
    let Some(mut current) = hex_to_bytes(s(att, "leaf_hash")) else {
        return false;
    };
    let Some(path) = inc.get("audit_path").and_then(Value::as_array) else {
        return false;
    };
    for item in path {
        let Some(sibling) = hex_to_bytes(s(item, "hash")) else {
            return false;
        };
        let mut h = Sha256::new();
        match s(item, "side") {
            "left" => {
                h.update(&sibling);
                h.update(&current);
            }
            "right" => {
                h.update(&current);
                h.update(&sibling);
            }
            _ => return false,
        }
        current = h.finalize().to_vec();
    }
    current.iter().map(|b| format!("{:02x}", b)).collect::<String>() == s(checkpoint, "root_hash")
}

fn version_parts(version: &str) -> Vec<i64> {
    version.split('.').map(|p| p.parse::<i64>().unwrap_or(0)).collect()
}

fn version_cmp(left: &str, right: &str) -> Ordering {
    let mut a = version_parts(left);
    let mut b = version_parts(right);
    let n = a.len().max(b.len());
    a.resize(n, 0);
    b.resize(n, 0);
    a.cmp(&b)
}

fn required_for(policy: &Value, channel: &str) -> BTreeMap<String, i64> {
    let obj = policy
        .get("required_predicates_by_channel")
        .and_then(|v| v.get(channel))
        .or_else(|| policy.get("default_required_predicates"))
        .and_then(Value::as_object);
    obj.map(|m| {
        m.iter()
            .map(|(k, v)| (k.clone(), v.as_i64().unwrap_or(0)))
            .collect()
    })
    .unwrap_or_default()
}

fn log_quorum(policy: &Value, channel: &str) -> i64 {
    policy
        .get("log_quorum_by_channel")
        .and_then(|v| v.get(channel))
        .and_then(Value::as_i64)
        .or_else(|| policy.get("default_log_quorum").and_then(Value::as_i64))
        .unwrap_or(0)
}

fn resilience_min_cost(policy: &Value, channel: &str) -> i64 {
    policy
        .get("resilience_min_cost_by_channel")
        .and_then(|v| v.get(channel))
        .and_then(Value::as_i64)
        .or_else(|| policy.get("default_resilience_min_cost").and_then(Value::as_i64))
        .unwrap_or(0)
}

#[derive(Clone)]
struct Evidence {
    predicate: String,
    signer_id: String,
    log_id: String,
    signer_domain: String,
    log_domain: String,
}

#[derive(Clone)]
struct CutResult {
    cost: i64,
    failure: String,
    failure_rank: usize,
    signer_domains: Vec<String>,
    log_domains: Vec<String>,
}

#[derive(Clone)]
struct RowState {
    artifact: Value,
    reasons: BTreeSet<String>,
    accepted: BTreeMap<String, BTreeMap<String, Value>>,
    logs: BTreeSet<String>,
    evidence: Vec<Evidence>,
    cut: Option<CutResult>,
    blockers: Vec<String>,
}

#[derive(Clone)]
struct FleetCutResult {
    cost: i64,
    directly_broken_artifacts: Vec<String>,
    broken_artifacts: Vec<String>,
    cascade_depth_by_artifact: BTreeMap<String, i64>,
    broken_impact_by_channel: BTreeMap<String, i64>,
    signer_domains: Vec<String>,
    log_domains: Vec<String>,
    recovery_breakpoint: Option<RecoveryBreakpoint>,
    recovery_margin: RecoveryMargin,
}

#[derive(Clone)]
struct RecoveryBreakpoint {
    count: usize,
    cost: i64,
    signer_domains: Vec<String>,
    log_domains: Vec<String>,
}

#[derive(Clone)]
struct RecoveryMargin {
    value: i64,
    restored_cost: i64,
    signer_domains: Vec<String>,
    log_domains: Vec<String>,
}

#[derive(Clone)]
struct FleetCandidate {
    artifact: Value,
    required: BTreeMap<String, i64>,
    quorum: i64,
    evidence: Vec<Evidence>,
}

fn evidence_broken(
    required: &BTreeMap<String, i64>,
    quorum: i64,
    evidence: &[Evidence],
    removed_signers: &BTreeSet<String>,
    removed_logs: &BTreeSet<String>,
) -> bool {
    let surviving: Vec<&Evidence> = evidence
        .iter()
        .filter(|row| {
            !removed_signers.contains(&row.signer_domain) && !removed_logs.contains(&row.log_domain)
        })
        .collect();
    for (predicate, threshold) in required {
        let signers = surviving
            .iter()
            .filter(|row| &row.predicate == predicate)
            .map(|row| row.signer_id.as_str())
            .collect::<BTreeSet<_>>();
        if signers.len() < *threshold as usize {
            return true;
        }
    }
    surviving
        .iter()
        .map(|row| row.log_id.as_str())
        .collect::<BTreeSet<_>>()
        .len()
        < quorum as usize
}

struct FleetOutcome {
    directly_broken: BTreeSet<String>,
    broken: BTreeSet<String>,
    cascade_depth_by_artifact: BTreeMap<String, i64>,
    broken_impact_by_channel: BTreeMap<String, i64>,
}

fn fleet_outcome(
    candidates: &BTreeMap<String, FleetCandidate>,
    targets: &BTreeMap<String, i64>,
    direct_targets: &BTreeMap<String, i64>,
    impact_targets: &BTreeMap<String, i64>,
    removed_signers: &BTreeSet<String>,
    removed_logs: &BTreeSet<String>,
) -> Option<FleetOutcome> {
    let directly_broken: BTreeSet<String> = candidates
        .iter()
        .filter(|(_, candidate)| {
            evidence_broken(
                &candidate.required,
                candidate.quorum,
                &candidate.evidence,
                removed_signers,
                removed_logs,
            )
        })
        .map(|(artifact_id, _)| artifact_id.clone())
        .collect();
    let mut broken = directly_broken.clone();
    let mut cascade_depth_by_artifact: BTreeMap<String, i64> = directly_broken
        .iter()
        .map(|artifact_id| (artifact_id.clone(), 0))
        .collect();
    let mut depth = 1i64;
    loop {
        let mut newly_broken = Vec::new();
        for (artifact_id, candidate) in candidates {
            if broken.contains(artifact_id) {
                continue;
            }
            let threshold = i(&candidate.artifact, "fleet_dependency_threshold");
            if threshold == 0 {
                continue;
            }
            let failed_weight: i64 = candidate
                .artifact
                .get("dependencies")
                .and_then(Value::as_array)
                .into_iter()
                .flatten()
                .filter(|dependency| {
                    let dependency_id = s(dependency, "artifact_id");
                    candidates.contains_key(dependency_id) && broken.contains(dependency_id)
                })
                .map(|dependency| i(dependency, "fleet_weight"))
                .sum();
            if failed_weight >= threshold {
                newly_broken.push(artifact_id.clone());
            }
        }
        if newly_broken.is_empty() {
            break;
        }
        for artifact_id in newly_broken {
            broken.insert(artifact_id.clone());
            cascade_depth_by_artifact.insert(artifact_id, depth);
        }
        depth += 1;
    }

    let mut broken_by_channel: BTreeMap<String, usize> =
        targets.keys().map(|channel| (channel.clone(), 0usize)).collect();
    let mut direct_by_channel: BTreeMap<String, usize> =
        targets.keys().map(|channel| (channel.clone(), 0usize)).collect();
    let mut broken_impact_by_channel: BTreeMap<String, i64> =
        targets.keys().map(|channel| (channel.clone(), 0i64)).collect();
    for artifact_id in &broken {
        let artifact = &candidates[artifact_id].artifact;
        let channel = s(artifact, "channel");
        *broken_by_channel.get_mut(channel).expect("target channel") += 1;
        *broken_impact_by_channel.get_mut(channel).expect("target channel") +=
            i(artifact, "fleet_impact");
    }
    for artifact_id in &directly_broken {
        let channel = s(&candidates[artifact_id].artifact, "channel");
        *direct_by_channel.get_mut(channel).expect("target channel") += 1;
    }
    if targets
        .iter()
        .any(|(channel, target)| broken_by_channel[channel] < *target as usize)
        || direct_targets
            .iter()
            .any(|(channel, target)| direct_by_channel[channel] < *target as usize)
        || impact_targets
            .iter()
            .any(|(channel, target)| broken_impact_by_channel[channel] < *target)
    {
        return None;
    }
    Some(FleetOutcome {
        directly_broken,
        broken,
        cascade_depth_by_artifact,
        broken_impact_by_channel,
    })
}

fn fleet_margin(
    outcome: &FleetOutcome,
    candidates: &BTreeMap<String, FleetCandidate>,
    targets: &BTreeMap<String, i64>,
    direct_targets: &BTreeMap<String, i64>,
    impact_targets: &BTreeMap<String, i64>,
) -> i64 {
    let mut slacks = Vec::new();
    for channel in targets.keys() {
        let direct_count = outcome
            .directly_broken
            .iter()
            .filter(|artifact_id| s(&candidates[*artifact_id].artifact, "channel") == channel)
            .count() as i64;
        let broken_count = outcome
            .broken
            .iter()
            .filter(|artifact_id| s(&candidates[*artifact_id].artifact, "channel") == channel)
            .count() as i64;
        slacks.push(direct_count - direct_targets[channel]);
        slacks.push(broken_count - targets[channel]);
        slacks.push(outcome.broken_impact_by_channel[channel] - impact_targets[channel]);
    }
    slacks.into_iter().min().unwrap_or(0)
}

fn minimum_fleet_cut(policy: &Value, states: &BTreeMap<String, RowState>) -> Option<FleetCutResult> {
    let target_map = |key: &str| -> BTreeMap<String, i64> {
        policy
            .get(key)
            .and_then(Value::as_object)
            .map(|object| {
                object
                    .iter()
                    .map(|(channel, target)| (channel.clone(), target.as_i64().unwrap_or(0)))
                    .collect()
            })
            .unwrap_or_default()
    };
    let targets = target_map("fleet_resilience_targets_by_channel");
    let direct_targets = target_map("fleet_resilience_direct_targets_by_channel");
    let impact_targets = target_map("fleet_resilience_impact_targets_by_channel");
    assert_eq!(targets.keys().collect::<Vec<_>>(), direct_targets.keys().collect::<Vec<_>>());
    assert_eq!(targets.keys().collect::<Vec<_>>(), impact_targets.keys().collect::<Vec<_>>());

    let empty = BTreeSet::new();
    let mut candidates: BTreeMap<String, FleetCandidate> = BTreeMap::new();
    for (artifact_id, state) in states {
        let channel = s(&state.artifact, "channel");
        if !targets.contains_key(channel) {
            continue;
        }
        let required = required_for(policy, channel);
        let quorum = log_quorum(policy, channel);
        if !evidence_broken(&required, quorum, &state.evidence, &empty, &empty) {
            candidates.insert(
                artifact_id.clone(),
                FleetCandidate {
                    artifact: state.artifact.clone(),
                    required,
                    quorum,
                    evidence: state.evidence.clone(),
                },
            );
        }
    }

    let signer_domains: Vec<String> = candidates
        .values()
        .flat_map(|candidate| candidate.evidence.iter().map(|row| row.signer_domain.clone()))
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    let log_domains: Vec<String> = candidates
        .values()
        .flat_map(|candidate| candidate.evidence.iter().map(|row| row.log_domain.clone()))
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    let domain_count = signer_domains.len() + log_domains.len();
    assert!(domain_count <= 18, "at most 18 relevant fleet resilience domains");

    let signer_costs = policy
        .get("signer_domain_costs")
        .and_then(Value::as_object)
        .expect("signer domain costs");
    let log_costs = policy
        .get("log_domain_costs")
        .and_then(Value::as_object)
        .expect("log domain costs");
    let mut best: Option<FleetCutResult> = None;
    for mask in 0u64..(1u64 << domain_count) {
        let mut removed_signers = BTreeSet::new();
        let mut removed_logs = BTreeSet::new();
        let mut cost = 0i64;
        for (index, domain) in signer_domains.iter().enumerate() {
            if mask & (1u64 << index) != 0 {
                removed_signers.insert(domain.clone());
                cost += signer_costs[domain].as_i64().expect("signer domain cost");
            }
        }
        for (offset, domain) in log_domains.iter().enumerate() {
            if mask & (1u64 << (signer_domains.len() + offset)) != 0 {
                removed_logs.insert(domain.clone());
                cost += log_costs[domain].as_i64().expect("log domain cost");
            }
        }

        let Some(outcome) = fleet_outcome(
            &candidates,
            &targets,
            &direct_targets,
            &impact_targets,
            &removed_signers,
            &removed_logs,
        ) else {
            continue;
        };
        // Recovery certificates only affect tie-breaking among cuts of the
        // same minimum cost.  Once a cheaper cut is known, avoid the
        // exponential recovery-submask search for this more expensive mask.
        if best.as_ref().is_some_and(|current| cost > current.cost) {
            continue;
        }
        let recovery_budget = i(policy, "fleet_recovery_domain_budget") as usize;
        let mut recovery_breakpoint: Option<RecoveryBreakpoint> = None;
        let mut recovery_margin = RecoveryMargin {
            value: fleet_margin(
                &outcome,
                &candidates,
                &targets,
                &direct_targets,
                &impact_targets,
            ),
            restored_cost: 0,
            signer_domains: Vec::new(),
            log_domains: Vec::new(),
        };
        let mut recovered_mask = mask;
        while recovered_mask != 0 {
            let recovered_count = recovered_mask.count_ones() as usize;
            let effective_mask = mask & !recovered_mask;
            let effective_signers: BTreeSet<String> = signer_domains
                .iter()
                .enumerate()
                .filter(|(index, _)| effective_mask & (1u64 << index) != 0)
                .map(|(_, domain)| domain.clone())
                .collect();
            let effective_logs: BTreeSet<String> = log_domains
                .iter()
                .enumerate()
                .filter(|(offset, _)| {
                    effective_mask & (1u64 << (signer_domains.len() + offset)) != 0
                })
                .map(|(_, domain)| domain.clone())
                .collect();
            let recovered_signers: Vec<String> = signer_domains
                .iter()
                .enumerate()
                .filter(|(index, _)| recovered_mask & (1u64 << index) != 0)
                .map(|(_, domain)| domain.clone())
                .collect();
            let recovered_logs: Vec<String> = log_domains
                .iter()
                .enumerate()
                .filter(|(offset, _)| {
                    recovered_mask & (1u64 << (signer_domains.len() + offset)) != 0
                })
                .map(|(_, domain)| domain.clone())
                .collect();
            let recovered_cost = recovered_signers
                .iter()
                .map(|domain| signer_costs[domain].as_i64().expect("signer domain cost"))
                .sum::<i64>()
                + recovered_logs
                    .iter()
                    .map(|domain| log_costs[domain].as_i64().expect("log domain cost"))
                    .sum::<i64>();
            let effective_outcome = fleet_outcome(
                &candidates,
                &targets,
                &direct_targets,
                &impact_targets,
                &effective_signers,
                &effective_logs,
            );
            if let Some(effective_outcome) = effective_outcome.as_ref() {
                if recovered_count <= recovery_budget {
                    let margin = RecoveryMargin {
                        value: fleet_margin(
                            effective_outcome,
                            &candidates,
                            &targets,
                            &direct_targets,
                            &impact_targets,
                        ),
                        restored_cost: recovered_cost,
                        signer_domains: recovered_signers.clone(),
                        log_domains: recovered_logs.clone(),
                    };
                    if (
                        margin.value,
                        margin.restored_cost,
                        &margin.signer_domains,
                        &margin.log_domains,
                    ) < (
                        recovery_margin.value,
                        recovery_margin.restored_cost,
                        &recovery_margin.signer_domains,
                        &recovery_margin.log_domains,
                    ) {
                        recovery_margin = margin;
                    }
                }
            } else {
                let breakpoint = RecoveryBreakpoint {
                    count: recovered_count,
                    cost: recovered_cost,
                    signer_domains: recovered_signers,
                    log_domains: recovered_logs,
                };
                let replace = recovery_breakpoint
                    .as_ref()
                    .map(|current| {
                        (
                            breakpoint.count,
                            breakpoint.cost,
                            &breakpoint.signer_domains,
                            &breakpoint.log_domains,
                        ) < (
                            current.count,
                            current.cost,
                            &current.signer_domains,
                            &current.log_domains,
                        )
                    })
                    .unwrap_or(true);
                if replace {
                    recovery_breakpoint = Some(breakpoint);
                }
            }
            recovered_mask = (recovered_mask - 1) & mask;
        }
        if recovery_breakpoint
            .as_ref()
            .map(|breakpoint| breakpoint.count <= recovery_budget)
            .unwrap_or(false)
        {
            continue;
        }
        let candidate = FleetCutResult {
            cost,
            directly_broken_artifacts: outcome.directly_broken.into_iter().collect(),
            broken_artifacts: outcome.broken.into_iter().collect(),
            cascade_depth_by_artifact: outcome.cascade_depth_by_artifact,
            broken_impact_by_channel: outcome.broken_impact_by_channel,
            signer_domains: removed_signers.into_iter().collect(),
            log_domains: removed_logs.into_iter().collect(),
            recovery_breakpoint,
            recovery_margin,
        };
        let replace = best
            .as_ref()
            .map(|current| {
                if candidate.cost != current.cost {
                    return candidate.cost < current.cost;
                }
                if candidate.recovery_margin.value != current.recovery_margin.value {
                    return candidate.recovery_margin.value > current.recovery_margin.value;
                }
                let candidate_breakpoint_count = candidate
                    .recovery_breakpoint
                    .as_ref()
                    .map(|breakpoint| breakpoint.count)
                    .unwrap_or(usize::MAX);
                let current_breakpoint_count = current
                    .recovery_breakpoint
                    .as_ref()
                    .map(|breakpoint| breakpoint.count)
                    .unwrap_or(usize::MAX);
                if candidate_breakpoint_count != current_breakpoint_count {
                    return candidate_breakpoint_count > current_breakpoint_count;
                }
                let candidate_breakpoint_cost = candidate
                    .recovery_breakpoint
                    .as_ref()
                    .map(|breakpoint| breakpoint.cost)
                    .unwrap_or(i64::MAX);
                let current_breakpoint_cost = current
                    .recovery_breakpoint
                    .as_ref()
                    .map(|breakpoint| breakpoint.cost)
                    .unwrap_or(i64::MAX);
                if candidate_breakpoint_cost != current_breakpoint_cost {
                    return candidate_breakpoint_cost > current_breakpoint_cost;
                }
                let candidate_count = candidate.signer_domains.len() + candidate.log_domains.len();
                let current_count = current.signer_domains.len() + current.log_domains.len();
                if candidate_count != current_count {
                    return candidate_count < current_count;
                }
                (&candidate.signer_domains, &candidate.log_domains)
                    < (&current.signer_domains, &current.log_domains)
            })
            .unwrap_or(true);
        if replace {
            best = Some(candidate);
        }
    }
    best
}

fn minimum_cut(
    policy: &Value,
    required: &BTreeMap<String, i64>,
    quorum: i64,
    evidence: &[Evidence],
) -> Option<CutResult> {
    let signer_costs = policy
        .get("signer_domain_costs")
        .and_then(Value::as_object)
        .expect("signer domain costs");
    let log_costs = policy
        .get("log_domain_costs")
        .and_then(Value::as_object)
        .expect("log domain costs");
    let signer_domains: Vec<String> = evidence
        .iter()
        .map(|e| e.signer_domain.clone())
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    let log_domains: Vec<String> = evidence
        .iter()
        .map(|e| e.log_domain.clone())
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    let domain_count = signer_domains.len() + log_domains.len();
    assert!(domain_count <= 16, "at most 16 relevant resilience domains");

    let predicate_order: Vec<String> = required.keys().cloned().collect();
    let mut best: Option<CutResult> = None;
    for mask in 0u64..(1u64 << domain_count) {
        let mut removed_signers = BTreeSet::new();
        let mut removed_logs = BTreeSet::new();
        let mut cost = 0i64;
        for (idx, domain) in signer_domains.iter().enumerate() {
            if mask & (1u64 << idx) != 0 {
                removed_signers.insert(domain.clone());
                cost += signer_costs
                    .get(domain)
                    .and_then(Value::as_i64)
                    .expect("signer domain cost");
            }
        }
        for (offset, domain) in log_domains.iter().enumerate() {
            if mask & (1u64 << (signer_domains.len() + offset)) != 0 {
                removed_logs.insert(domain.clone());
                cost += log_costs
                    .get(domain)
                    .and_then(Value::as_i64)
                    .expect("log domain cost");
            }
        }

        let surviving: Vec<&Evidence> = evidence
            .iter()
            .filter(|e| !removed_signers.contains(&e.signer_domain) && !removed_logs.contains(&e.log_domain))
            .collect();
        let mut failure = None;
        for (rank, predicate) in predicate_order.iter().enumerate() {
            let signers = surviving
                .iter()
                .filter(|e| &e.predicate == predicate)
                .map(|e| e.signer_id.as_str())
                .collect::<BTreeSet<_>>();
            if signers.len() < required[predicate] as usize {
                failure = Some((format!("threshold:{predicate}"), rank));
                break;
            }
        }
        if failure.is_none() {
            let logs = surviving.iter().map(|e| e.log_id.as_str()).collect::<BTreeSet<_>>();
            if logs.len() < quorum as usize {
                failure = Some(("log_quorum".to_string(), predicate_order.len()));
            }
        }
        let Some((failure, failure_rank)) = failure else {
            continue;
        };
        let candidate = CutResult {
            cost,
            failure,
            failure_rank,
            signer_domains: removed_signers.into_iter().collect(),
            log_domains: removed_logs.into_iter().collect(),
        };
        let candidate_key = (
            candidate.cost,
            candidate.signer_domains.len() + candidate.log_domains.len(),
            candidate.failure_rank,
            &candidate.signer_domains,
            &candidate.log_domains,
        );
        let replace = best
            .as_ref()
            .map(|current| {
                candidate_key
                    < (
                        current.cost,
                        current.signer_domains.len() + current.log_domains.len(),
                        current.failure_rank,
                        &current.signer_domains,
                        &current.log_domains,
                    )
            })
            .unwrap_or(true);
        if replace {
            best = Some(candidate);
        }
    }
    best
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 {
        eprintln!("usage: logseal <input_dir> <output_dir>");
        std::process::exit(2);
    }
    let input = Path::new(&args[1]);
    let output = Path::new(&args[2]);
    fs::create_dir_all(output).expect("create output dir");

    let policy = read_json(input.join("policy.json"));
    let eval_time = s(&policy, "evaluation_time").to_string();
    let logs: HashMap<String, Value> = read_jsonl(input.join("trusted_logs.jsonl"))
        .into_iter()
        .map(|v| (s(&v, "log_id").to_string(), v))
        .collect();
    let signers: HashMap<String, Value> = read_jsonl(input.join("signers.jsonl"))
        .into_iter()
        .map(|v| (s(&v, "signer_id").to_string(), v))
        .collect();
    let artifacts = read_jsonl(input.join("artifacts.jsonl"));
    let attestations = read_jsonl(input.join("attestations.jsonl"));
    let checkpoints: HashMap<String, Value> = read_jsonl(input.join("checkpoints.jsonl"))
        .into_iter()
        .map(|v| (s(&v, "checkpoint_id").to_string(), v))
        .collect();
    let inclusions: HashMap<String, Value> = read_jsonl(input.join("inclusions.jsonl"))
        .into_iter()
        .map(|v| (s(&v, "attestation_id").to_string(), v))
        .collect();
    let revocations = read_jsonl(input.join("revocations.jsonl"));

    let revoked = |kind: &str| -> HashSet<String> {
        revocations
            .iter()
            .filter(|r| s(r, "kind") == kind && s(r, "effective_at") <= eval_time.as_str())
            .map(|r| s(r, "target_id").to_string())
            .collect()
    };
    let revoked_signers = revoked("signer");
    let revoked_atts = revoked("attestation");
    let revoked_logs = revoked("log");
    let revoked_checkpoints = revoked("checkpoint");

    let mut states: BTreeMap<String, RowState> = BTreeMap::new();

    for artifact in &artifacts {
        let required = required_for(&policy, s(artifact, "channel"));
        let mut state = RowState {
            artifact: artifact.clone(),
            reasons: BTreeSet::new(),
            accepted: required.keys().map(|p| (p.clone(), BTreeMap::new())).collect(),
            logs: BTreeSet::new(),
            evidence: Vec::new(),
            cut: None,
            blockers: Vec::new(),
        };

        for att in attestations.iter().filter(|a| s(a, "artifact_id") == s(artifact, "artifact_id")) {
            let mut usable = true;
            let payload = att_payload(att);
            let signer = signers.get(s(att, "signer_id"));
            if let Some(signer) = signer {
                if signed_hex(s(signer, "key_secret"), &payload) != s(att, "signature") {
                    state.reasons.insert("bad_signature".to_string());
                    usable = false;
                }
                if s(signer, "role") != "release" {
                    state.reasons.insert("wrong_role".to_string());
                    usable = false;
                }
                let scopes = string_array(signer, "artifact_scopes");
                if !scopes.iter().any(|x| x == "*") && !scopes.iter().any(|x| x == s(artifact, "artifact_id")) {
                    state.reasons.insert("scope_mismatch".to_string());
                    usable = false;
                }
                if !string_array(signer, "cohorts").iter().any(|x| x == s(artifact, "cohort")) {
                    state.reasons.insert("cohort_scope".to_string());
                    usable = false;
                }
                if !string_array(signer, "predicates").iter().any(|x| x == s(att, "predicate")) {
                    state.reasons.insert("predicate_scope".to_string());
                    usable = false;
                }
                if !(s(signer, "not_before") <= s(att, "issued_at") && s(att, "issued_at") <= s(signer, "not_after")) {
                    state.reasons.insert("signer_time_window".to_string());
                    usable = false;
                }
                if revoked_signers.contains(s(signer, "signer_id")) {
                    state.reasons.insert("revoked_signer".to_string());
                    usable = false;
                }
            } else {
                state.reasons.insert("unknown_signer".to_string());
                usable = false;
            }

            if s(att, "digest") != s(artifact, "digest") {
                state.reasons.insert("digest_mismatch".to_string());
                usable = false;
            }
            if s(att, "artifact_version") != s(artifact, "version") {
                state.reasons.insert("version_mismatch".to_string());
                usable = false;
            }
            if revoked_atts.contains(s(att, "attestation_id")) {
                state.reasons.insert("revoked_attestation".to_string());
                usable = false;
            }

            let log = logs.get(s(att, "log_id"));
            let checkpoint = checkpoints.get(s(att, "checkpoint_id"));
            if log.is_none() {
                state.reasons.insert("unknown_log".to_string());
                usable = false;
            }
            if checkpoint.is_none() {
                state.reasons.insert("unknown_checkpoint".to_string());
                usable = false;
            }
            if revoked_logs.contains(s(att, "log_id")) {
                state.reasons.insert("revoked_log".to_string());
                usable = false;
            }
            if let Some(cp) = checkpoint {
                if s(cp, "log_id") != s(att, "log_id") {
                    state.reasons.insert("checkpoint_log_mismatch".to_string());
                    usable = false;
                }
                if let Some(log) = log {
                    if signed_hex(s(log, "log_secret"), &checkpoint_payload(cp)) != s(cp, "signature") {
                        state.reasons.insert("bad_checkpoint_signature".to_string());
                        usable = false;
                    }
                    if !(s(log, "not_before") <= s(cp, "signed_at") && s(cp, "signed_at") <= s(log, "not_after")) {
                        state.reasons.insert("checkpoint_time_window".to_string());
                        usable = false;
                    }
                }
                if s(cp, "signed_at") > eval_time.as_str() {
                    state.reasons.insert("checkpoint_after_evaluation".to_string());
                    usable = false;
                }
                if revoked_checkpoints.contains(s(cp, "checkpoint_id")) {
                    state.reasons.insert("revoked_checkpoint".to_string());
                    usable = false;
                }
                if sha256_hex(&payload) != s(att, "leaf_hash") {
                    state.reasons.insert("leaf_hash_mismatch".to_string());
                    usable = false;
                }
                if !inclusion_ok(att, inclusions.get(s(att, "attestation_id")), cp) {
                    state.reasons.insert("bad_inclusion_proof".to_string());
                    usable = false;
                }
            }

            if !state.accepted.contains_key(s(att, "predicate")) {
                usable = false;
            }
            if usable {
                let per_pred = state.accepted.get_mut(s(att, "predicate")).expect("predicate");
                let current = per_pred.get(s(att, "signer_id"));
                let keep = current
                    .map(|cur| {
                        s(att, "issued_at") > s(cur, "issued_at")
                            || (s(att, "issued_at") == s(cur, "issued_at")
                                && s(att, "attestation_id") < s(cur, "attestation_id"))
                    })
                    .unwrap_or(true);
                if keep {
                    per_pred.insert(s(att, "signer_id").to_string(), att.clone());
                }
                state.logs.insert(s(att, "log_id").to_string());
                state.evidence.push(Evidence {
                    predicate: s(att, "predicate").to_string(),
                    signer_id: s(att, "signer_id").to_string(),
                    log_id: s(att, "log_id").to_string(),
                    signer_domain: s(signer.expect("usable signer"), "trust_domain").to_string(),
                    log_domain: s(log.expect("usable log"), "operator_domain").to_string(),
                });
            }
        }

        for (predicate, threshold) in &required {
            if state.accepted.get(predicate).map(BTreeMap::len).unwrap_or(0) < *threshold as usize {
                state.reasons.insert(format!("threshold:{predicate}"));
            }
        }
        if state.logs.len() < log_quorum(&policy, s(artifact, "channel")) as usize {
            state.reasons.insert("log_quorum".to_string());
        }
        state.cut = minimum_cut(
            &policy,
            &required,
            log_quorum(&policy, s(artifact, "channel")),
            &state.evidence,
        );
        if state
            .cut
            .as_ref()
            .map(|cut| cut.cost < resilience_min_cost(&policy, s(artifact, "channel")))
            .unwrap_or(false)
        {
            state.reasons.insert("resilience_shortfall".to_string());
        }
        if eval_time.as_str() < s(artifact, "rollout_start") || eval_time.as_str() > s(artifact, "rollout_end") {
            state.reasons.insert("rollout_window".to_string());
        }
        let allowed = policy
            .get("allowed_cohorts_by_channel")
            .and_then(|v| v.get(s(artifact, "channel")))
            .and_then(Value::as_array)
            .map(|a| a.iter().filter_map(Value::as_str).any(|x| x == s(artifact, "cohort")))
            .unwrap_or(false);
        if !allowed {
            state.reasons.insert("cohort_not_allowed".to_string());
        }

        states.insert(s(artifact, "artifact_id").to_string(), state);
    }

    let first_phase: HashMap<String, BTreeSet<String>> = states
        .iter()
        .map(|(id, st)| (id.clone(), st.reasons.clone()))
        .collect();
    for artifact in &artifacts {
        let mut blockers = Vec::new();
        if let Some(deps) = artifact.get("dependencies").and_then(Value::as_array) {
            for dep in deps {
                let id = s(dep, "artifact_id");
                if let Some(target) = states.get(id) {
                    if first_phase.get(id).map(|r| !r.is_empty()).unwrap_or(false) {
                        blockers.push(format!("rejected:{id}"));
                    } else if version_cmp(s(&target.artifact, "version"), s(dep, "min_version")) == Ordering::Less {
                        blockers.push(format!("version:{id}"));
                    } else if !string_array(dep, "allowed_channels").iter().any(|c| c == s(&target.artifact, "channel")) {
                        blockers.push(format!("channel:{id}"));
                    }
                } else {
                    blockers.push(format!("missing:{id}"));
                }
            }
        }
        if !blockers.is_empty() {
            let st = states.get_mut(s(artifact, "artifact_id")).expect("state");
            st.reasons.insert("dependency_blocked".to_string());
            st.blockers = blockers;
        }
    }

    let mut rows = Vec::new();
    for artifact in &artifacts {
        let st = states.get(s(artifact, "artifact_id")).expect("state");
        let required = required_for(&policy, s(artifact, "channel"));
        let mut reason_order: Vec<String> = [
            "bad_signature",
            "unknown_signer",
            "wrong_role",
            "scope_mismatch",
            "cohort_scope",
            "predicate_scope",
            "signer_time_window",
            "digest_mismatch",
            "version_mismatch",
            "revoked_signer",
            "revoked_attestation",
            "unknown_log",
            "unknown_checkpoint",
            "checkpoint_log_mismatch",
            "bad_checkpoint_signature",
            "checkpoint_time_window",
            "checkpoint_after_evaluation",
            "revoked_log",
            "revoked_checkpoint",
            "leaf_hash_mismatch",
            "bad_inclusion_proof",
        ]
        .iter()
        .map(|x| x.to_string())
        .collect();
        reason_order.extend(required.keys().map(|p| format!("threshold:{p}")));
        reason_order.extend([
            "log_quorum".to_string(),
            "resilience_shortfall".to_string(),
            "rollout_window".to_string(),
            "cohort_not_allowed".to_string(),
            "dependency_blocked".to_string(),
        ]);
        let reasons: Vec<String> = reason_order
            .into_iter()
            .filter(|reason| st.reasons.contains(reason))
            .collect();
        let mut accepted_signers = Map::new();
        for predicate in required.keys() {
            accepted_signers.insert(
                predicate.clone(),
                json!(st.accepted.get(predicate).map(|m| m.keys().cloned().collect::<Vec<_>>()).unwrap_or_default()),
            );
        }
        let resilience_cut = st
            .cut
            .as_ref()
            .map(|cut| {
                json!({
                    "cost": cut.cost,
                    "failure": cut.failure,
                    "signer_domains": cut.signer_domains,
                    "log_domains": cut.log_domains,
                })
            })
            .unwrap_or_else(|| {
                json!({
                    "cost": Value::Null,
                    "failure": Value::Null,
                    "signer_domains": Vec::<String>::new(),
                    "log_domains": Vec::<String>::new(),
                })
            });
        rows.push(json!({
            "artifact_id": s(artifact, "artifact_id"),
            "version": s(artifact, "version"),
            "channel": s(artifact, "channel"),
            "cohort": s(artifact, "cohort"),
            "status": if reasons.is_empty() { "accepted" } else { "rejected" },
            "reasons": reasons,
            "accepted_signers": accepted_signers,
            "accepted_logs": st.logs.iter().cloned().collect::<Vec<_>>(),
            "resilience_cut": resilience_cut,
            "dependency_blockers": st.blockers,
        }));
    }

    let priority: HashMap<String, usize> = policy
        .get("channel_priority")
        .and_then(Value::as_array)
        .map(|a| {
            a.iter()
                .filter_map(Value::as_str)
                .enumerate()
                .map(|(idx, channel)| (channel.to_string(), idx))
                .collect()
        })
        .unwrap_or_default();
    rows.sort_by(|a, b| {
        if s(&policy, "ordering") == "channel_priority" {
            let ar = if priority.contains_key(s(a, "channel")) { 0 } else { 1 };
            let br = if priority.contains_key(s(b, "channel")) { 0 } else { 1 };
            ar.cmp(&br)
                .then_with(|| {
                    if ar == 0 {
                        priority[s(a, "channel")].cmp(&priority[s(b, "channel")])
                    } else {
                        s(a, "channel").cmp(s(b, "channel"))
                    }
                })
                .then_with(|| s(a, "artifact_id").cmp(s(b, "artifact_id")))
                .then_with(|| version_cmp(s(a, "version"), s(b, "version")))
                .then_with(|| s(a, "cohort").cmp(s(b, "cohort")))
        } else {
            s(a, "artifact_id")
                .cmp(s(b, "artifact_id"))
                .then_with(|| version_cmp(s(a, "version"), s(b, "version")))
                .then_with(|| s(a, "channel").cmp(s(b, "channel")))
                .then_with(|| s(a, "cohort").cmp(s(b, "cohort")))
        }
    });

    let accepted = rows.iter().filter(|r| s(r, "status") == "accepted").count();
    let fleet_resilience_cut = minimum_fleet_cut(&policy, &states)
        .map(|cut| {
            let recovery_breakpoint = cut.recovery_breakpoint.map(|breakpoint| {
                json!({
                    "count": breakpoint.count,
                    "cost": breakpoint.cost,
                    "signer_domains": breakpoint.signer_domains,
                    "log_domains": breakpoint.log_domains,
                })
            });
            let recovery_margin = json!({
                "value": cut.recovery_margin.value,
                "restored_cost": cut.recovery_margin.restored_cost,
                "signer_domains": cut.recovery_margin.signer_domains,
                "log_domains": cut.recovery_margin.log_domains,
            });
            json!({
                "cost": cut.cost,
                "shortfall": cut.cost < i(&policy, "fleet_resilience_min_cost"),
                "directly_broken_artifacts": cut.directly_broken_artifacts,
                "broken_artifacts": cut.broken_artifacts,
                "cascade_depth_by_artifact": cut.cascade_depth_by_artifact,
                "broken_impact_by_channel": cut.broken_impact_by_channel,
                "signer_domains": cut.signer_domains,
                "log_domains": cut.log_domains,
                "recovery_breakpoint": recovery_breakpoint,
                "recovery_margin": recovery_margin,
            })
        })
        .unwrap_or_else(|| {
            json!({
                "cost": Value::Null,
                "shortfall": false,
                "directly_broken_artifacts": Vec::<String>::new(),
                "broken_artifacts": Vec::<String>::new(),
                "cascade_depth_by_artifact": BTreeMap::<String, i64>::new(),
                "broken_impact_by_channel": policy
                    .get("fleet_resilience_targets_by_channel")
                    .and_then(Value::as_object)
                    .map(|targets| targets.keys().map(|channel| (channel.clone(), 0i64)).collect::<BTreeMap<_, _>>())
                    .unwrap_or_default(),
                "signer_domains": Vec::<String>::new(),
                "log_domains": Vec::<String>::new(),
                "recovery_breakpoint": Value::Null,
                "recovery_margin": Value::Null,
            })
        });
    let report = json!({
        "generated_at": eval_time,
        "artifacts": rows,
        "fleet_resilience_cut": fleet_resilience_cut,
        "summary": {"accepted": accepted, "rejected": artifacts.len() - accepted, "total": artifacts.len()}
    });
    fs::write(
        output.join("report.json"),
        serde_json::to_string_pretty(&report).expect("serialize report"),
    )
    .expect("write report");
}

//! Input loading and structural validation (fatal errors).

use std::collections::{HashMap, HashSet, VecDeque};
use std::fs;
use std::path::Path;

use serde_json::Value;

use crate::crypto_helpers::parse_sec1_verifying_key;
use crate::hexutil::{decode_lower_hex, require_exact_lower_hex};
use crate::quote_parse::SUPPORTED_PCRS;

#[derive(Debug, Clone)]
pub struct Device {
    pub device_id: String,
    pub device_class: String,
    pub last_reset_count: u32,
    pub last_restart_count: u32,
    pub last_clock: u64,
}

#[derive(Debug, Clone)]
pub struct AttestationKey {
    pub attestation_key_id: String,
    pub device_id: String,
    pub qualified_name_hex: String,
    pub qualified_name: Vec<u8>,
    pub public_key_sec1_hex: String,
    pub public_key_sec1: Vec<u8>,
    pub valid_from: u64,
    pub valid_until: u64,
}

#[derive(Debug, Clone)]
pub struct MeasurementRule {
    pub rule_id: String,
    pub kind: String,
    pub pcr_index: u32,
    pub event_type: String,
    pub component: String,
    pub allowed_versions: Vec<String>,
    pub allowed_digests: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct OrderConstraint {
    pub before_rule_id: String,
    pub after_rule_id: String,
}

#[derive(Debug, Clone)]
pub struct Policy {
    pub policy_id: String,
    pub allowed_device_classes: Vec<String>,
    pub required_pcrs: Vec<u32>,
    pub allowed_firmware_versions: Vec<u64>,
    pub require_safe: bool,
    pub unknown_event_mode: String,
    pub measurement_rules: HashMap<String, MeasurementRule>,
    pub order_constraints: Vec<OrderConstraint>,
}

#[derive(Debug, Clone)]
pub struct Event {
    pub event_seq: u32,
    pub pcr_index: u32,
    pub event_type: String,
    pub component: String,
    pub version: String,
    pub measurement_digest: String,
}

#[derive(Debug, Clone)]
pub struct EventLog {
    pub event_log_id: String,
    pub device_id: String,
    pub events: Vec<Event>,
}

#[derive(Debug, Clone)]
pub struct Nonce {
    pub nonce_id: String,
    pub device_id: String,
    pub nonce_hex: String,
    pub nonce_bytes: Vec<u8>,
    pub issued_at: u64,
    pub expires_at: u64,
    pub initially_consumed_by_request_id_or_null: Option<String>,
}

#[derive(Debug, Clone)]
pub struct Request {
    pub request_id: String,
    pub received_at: u64,
    pub device_id: String,
    pub attestation_key_id: String,
    pub nonce_id: String,
    pub policy_id: String,
    pub event_log_id: String,
    pub quote_hex: String,
    pub signature_hex: String,
    pub quote_bytes: Vec<u8>,
    pub signature_bytes: Vec<u8>,
}

#[derive(Debug, Clone)]
pub struct PolicyLimits {
    pub maximum_devices: u32,
    pub maximum_attestation_keys: u32,
    pub maximum_reference_policies: u32,
    pub maximum_event_logs: u32,
    pub maximum_events_per_log: u32,
    pub maximum_total_events: u32,
    pub maximum_nonce_challenges: u32,
    pub maximum_requests: u32,
    pub maximum_quote_bytes: u32,
    pub maximum_signature_bytes: u32,
}

#[derive(Debug, Clone)]
pub struct Dataset {
    pub devices: HashMap<String, Device>,
    pub keys: HashMap<String, AttestationKey>,
    pub policies: HashMap<String, Policy>,
    pub event_logs: HashMap<String, EventLog>,
    pub nonces: HashMap<String, Nonce>,
    pub requests: Vec<Request>,
    pub policy_limits: PolicyLimits,
}

fn norm_id(v: &Value, field: &str) -> Result<String, String> {
    let s = v
        .as_str()
        .ok_or_else(|| format!("{field} must be string"))?;
    let s = s.trim();
    if s.is_empty() {
        return Err(format!("{field} empty"));
    }
    Ok(s.to_string())
}

fn u32_val(v: &Value, field: &str) -> Result<u32, String> {
    if v.is_boolean() {
        return Err(format!("{field} must be integer"));
    }
    let n = match v {
        Value::Number(n) => n,
        _ => return Err(format!("{field} must be integer")),
    };
    let u = n
        .as_u64()
        .or_else(|| n.as_i64().filter(|&i| i >= 0).map(|i| i as u64))
        .ok_or_else(|| format!("{field} must be integer"))?;
    if u > 0xffff_ffff {
        return Err(format!("{field} out of u32 range"));
    }
    Ok(u as u32)
}

fn u64_val(v: &Value, field: &str) -> Result<u64, String> {
    if v.is_boolean() {
        return Err(format!("{field} must be integer"));
    }
    let n = match v {
        Value::Number(n) => n,
        _ => return Err(format!("{field} must be integer")),
    };
    if let Some(u) = n.as_u64() {
        return Ok(u);
    }
    if let Some(i) = n.as_i64() {
        if i < 0 {
            return Err(format!("{field} out of u64 range"));
        }
        return Ok(i as u64);
    }
    Err(format!("{field} must be integer"))
}

fn expect_keys(obj: &Value, required: &[&str], label: &str) -> Result<(), String> {
    let map = obj
        .as_object()
        .ok_or_else(|| format!("{label} must be object"))?;
    let keys: HashSet<&str> = map.keys().map(|k| k.as_str()).collect();
    let req: HashSet<&str> = required.iter().copied().collect();
    let missing: Vec<&str> = req.difference(&keys).copied().collect();
    let extra: Vec<&str> = keys.difference(&req).copied().collect();
    if !missing.is_empty() {
        let mut m = missing;
        m.sort_unstable();
        // Match Python: f"... missing fields: {sorted(missing)}" with single-quoted items.
        let formatted = format!(
            "[{}]",
            m.iter()
                .map(|s| format!("'{s}'"))
                .collect::<Vec<_>>()
                .join(", ")
        );
        return Err(format!("{label} missing fields: {formatted}"));
    }
    if !extra.is_empty() {
        let mut e = extra;
        e.sort_unstable();
        let formatted = format!(
            "[{}]",
            e.iter()
                .map(|s| format!("'{s}'"))
                .collect::<Vec<_>>()
                .join(", ")
        );
        return Err(format!("{label} unknown fields: {formatted}"));
    }
    Ok(())
}

fn sorted_unique_strs(arr: &Value, field: &str) -> Result<Vec<String>, String> {
    let list = arr
        .as_array()
        .ok_or_else(|| format!("{field} must be array"))?;
    let mut out = Vec::new();
    let mut seen = HashSet::new();
    for (i, x) in list.iter().enumerate() {
        let s = x
            .as_str()
            .ok_or_else(|| format!("{field}[{i}] must be string"))?;
        let s = s.trim();
        if s.is_empty() {
            return Err(format!("{field}[{i}] empty"));
        }
        if !seen.insert(s.to_string()) {
            return Err(format!("{field} duplicate"));
        }
        out.push(s.to_string());
    }
    out.sort();
    Ok(out)
}

fn has_cycle(edges: &[(String, String)]) -> bool {
    let mut graph: HashMap<String, Vec<String>> = HashMap::new();
    let mut nodes: HashSet<String> = HashSet::new();
    for (a, b) in edges {
        graph.entry(a.clone()).or_default().push(b.clone());
        nodes.insert(a.clone());
        nodes.insert(b.clone());
    }
    let mut indeg: HashMap<String, usize> = nodes.iter().map(|n| (n.clone(), 0)).collect();
    for (a, b) in edges {
        *indeg.entry(b.clone()).or_insert(0) += 1;
        indeg.entry(a.clone()).or_insert(0);
    }
    let mut q: VecDeque<String> = indeg
        .iter()
        .filter(|(_, d)| **d == 0)
        .map(|(n, _)| n.clone())
        .collect();
    let mut seen = 0usize;
    while let Some(n) = q.pop_front() {
        seen += 1;
        if let Some(ms) = graph.get(&n) {
            for m in ms {
                let e = indeg.get_mut(m).unwrap();
                *e -= 1;
                if *e == 0 {
                    q.push_back(m.clone());
                }
            }
        }
    }
    seen != nodes.len()
}

fn supported_pcr(p: u32) -> bool {
    SUPPORTED_PCRS.contains(&p)
}

fn jload(data_dir: &Path, name: &str) -> Result<Value, String> {
    let path = data_dir.join(name);
    let bytes = fs::read(&path).map_err(|e| format!("unreadable JSON {name}: {e}"))?;
    let text = String::from_utf8(bytes).map_err(|e| format!("unreadable JSON {name}: {e}"))?;
    serde_json::from_str(&text).map_err(|e| format!("unreadable JSON {name}: {e}"))
}

fn map_hex_err(e: String) -> String {
    e
}

pub fn load_dataset(data_dir: &Path) -> Result<Dataset, String> {
    let limits_v = jload(data_dir, "policy.json")?;
    expect_keys(
        &limits_v,
        &[
            "maximum_devices",
            "maximum_attestation_keys",
            "maximum_reference_policies",
            "maximum_event_logs",
            "maximum_events_per_log",
            "maximum_total_events",
            "maximum_nonce_challenges",
            "maximum_requests",
            "maximum_quote_bytes",
            "maximum_signature_bytes",
        ],
        "policy.json",
    )?;
    let limits = PolicyLimits {
        maximum_devices: u32_val(&limits_v["maximum_devices"], "maximum_devices")?,
        maximum_attestation_keys: u32_val(
            &limits_v["maximum_attestation_keys"],
            "maximum_attestation_keys",
        )?,
        maximum_reference_policies: u32_val(
            &limits_v["maximum_reference_policies"],
            "maximum_reference_policies",
        )?,
        maximum_event_logs: u32_val(&limits_v["maximum_event_logs"], "maximum_event_logs")?,
        maximum_events_per_log: u32_val(
            &limits_v["maximum_events_per_log"],
            "maximum_events_per_log",
        )?,
        maximum_total_events: u32_val(&limits_v["maximum_total_events"], "maximum_total_events")?,
        maximum_nonce_challenges: u32_val(
            &limits_v["maximum_nonce_challenges"],
            "maximum_nonce_challenges",
        )?,
        maximum_requests: u32_val(&limits_v["maximum_requests"], "maximum_requests")?,
        maximum_quote_bytes: u32_val(&limits_v["maximum_quote_bytes"], "maximum_quote_bytes")?,
        maximum_signature_bytes: u32_val(
            &limits_v["maximum_signature_bytes"],
            "maximum_signature_bytes",
        )?,
    };

    let devices_raw = jload(data_dir, "devices.json")?;
    let devices_arr = devices_raw
        .as_array()
        .ok_or_else(|| "devices.json must be array".to_string())?;
    if devices_arr.len() as u32 > limits.maximum_devices {
        return Err("maximum_devices exceeded".into());
    }
    let mut devices: HashMap<String, Device> = HashMap::new();
    for (i, rec) in devices_arr.iter().enumerate() {
        expect_keys(
            rec,
            &[
                "device_id",
                "device_class",
                "last_reset_count",
                "last_restart_count",
                "last_clock",
            ],
            &format!("devices[{i}]"),
        )?;
        let did = norm_id(&rec["device_id"], "device_id")?;
        if devices.contains_key(&did) {
            return Err(format!("duplicate device_id {did}"));
        }
        devices.insert(
            did.clone(),
            Device {
                device_id: did,
                device_class: norm_id(&rec["device_class"], "device_class")?,
                last_reset_count: u32_val(&rec["last_reset_count"], "last_reset_count")?,
                last_restart_count: u32_val(&rec["last_restart_count"], "last_restart_count")?,
                last_clock: u64_val(&rec["last_clock"], "last_clock")?,
            },
        );
    }

    let keys_raw = jload(data_dir, "attestation_keys.json")?;
    let keys_arr = keys_raw
        .as_array()
        .ok_or_else(|| "attestation_keys.json must be array".to_string())?;
    if keys_arr.len() as u32 > limits.maximum_attestation_keys {
        return Err("maximum_attestation_keys exceeded".into());
    }
    let mut keys: HashMap<String, AttestationKey> = HashMap::new();
    for (i, rec) in keys_arr.iter().enumerate() {
        expect_keys(
            rec,
            &[
                "attestation_key_id",
                "device_id",
                "qualified_name_hex",
                "public_key_sec1_hex",
                "valid_from",
                "valid_until",
            ],
            &format!("keys[{i}]"),
        )?;
        let kid = norm_id(&rec["attestation_key_id"], "attestation_key_id")?;
        if keys.contains_key(&kid) {
            return Err(format!("duplicate attestation_key_id {kid}"));
        }
        let did = norm_id(&rec["device_id"], "device_id")?;
        if !devices.contains_key(&did) {
            return Err(format!("unknown device_id in key {kid}"));
        }
        let qn_hex = rec["qualified_name_hex"]
            .as_str()
            .ok_or_else(|| "qualified_name_hex must be string".to_string())?;
        let pk_hex = rec["public_key_sec1_hex"]
            .as_str()
            .ok_or_else(|| "public_key_sec1_hex must be string".to_string())?;
        let qn = require_exact_lower_hex(qn_hex, 34).map_err(map_hex_err)?;
        let pk = require_exact_lower_hex(pk_hex, 65).map_err(map_hex_err)?;
        parse_sec1_verifying_key(&pk)
            .map_err(|e| format!("invalid public key {kid}: {e}"))?;
        let vf = u64_val(&rec["valid_from"], "valid_from")?;
        let vu = u64_val(&rec["valid_until"], "valid_until")?;
        if vf > vu {
            return Err(format!("valid_from > valid_until for {kid}"));
        }
        keys.insert(
            kid.clone(),
            AttestationKey {
                attestation_key_id: kid,
                device_id: did,
                qualified_name_hex: qn_hex.to_string(),
                qualified_name: qn,
                public_key_sec1_hex: pk_hex.to_string(),
                public_key_sec1: pk,
                valid_from: vf,
                valid_until: vu,
            },
        );
    }

    let pols_raw = jload(data_dir, "reference_policies.json")?;
    let pols_arr = pols_raw
        .as_array()
        .ok_or_else(|| "reference_policies.json must be array".to_string())?;
    if pols_arr.len() as u32 > limits.maximum_reference_policies {
        return Err("maximum_reference_policies exceeded".into());
    }
    let mut policies: HashMap<String, Policy> = HashMap::new();
    for (i, rec) in pols_arr.iter().enumerate() {
        expect_keys(
            rec,
            &[
                "policy_id",
                "allowed_device_classes",
                "required_pcrs",
                "allowed_firmware_versions",
                "require_safe",
                "unknown_event_mode",
                "measurement_rules",
                "order_constraints",
            ],
            &format!("policies[{i}]"),
        )?;
        let pid = norm_id(&rec["policy_id"], "policy_id")?;
        if policies.contains_key(&pid) {
            return Err(format!("duplicate policy_id {pid}"));
        }
        let classes_v = rec["allowed_device_classes"]
            .as_array()
            .ok_or_else(|| format!("allowed_device_classes for {pid}"))?;
        if classes_v.is_empty() {
            return Err(format!("allowed_device_classes for {pid}"));
        }
        let mut classes = Vec::new();
        for x in classes_v {
            classes.push(norm_id(x, "device_class")?);
        }
        let class_set: HashSet<&str> = classes.iter().map(|s| s.as_str()).collect();
        if class_set.len() != classes.len() {
            return Err("duplicate allowed_device_classes".into());
        }
        let req_pcrs_v = rec["required_pcrs"]
            .as_array()
            .ok_or_else(|| "required_pcrs empty".to_string())?;
        if req_pcrs_v.is_empty() {
            return Err("required_pcrs empty".into());
        }
        let mut req_pcrs: Vec<u32> = Vec::new();
        for p in req_pcrs_v {
            let p = u32_val(p, "pcr")?;
            if !supported_pcr(p) {
                return Err("unsupported required pcr".into());
            }
            if req_pcrs.contains(&p) {
                return Err("duplicate required pcr".into());
            }
            req_pcrs.push(p);
        }
        req_pcrs.sort_unstable();
        let require_safe = rec["require_safe"]
            .as_bool()
            .ok_or_else(|| "require_safe must be bool".to_string())?;
        let mode = rec["unknown_event_mode"]
            .as_str()
            .ok_or_else(|| "unknown_event_mode".to_string())?;
        if mode != "allow" && mode != "reject" {
            return Err("unknown_event_mode".into());
        }
        let fw_v = rec["allowed_firmware_versions"]
            .as_array()
            .ok_or_else(|| "allowed_firmware_versions".to_string())?;
        let mut fw: Vec<u64> = Vec::new();
        for x in fw_v {
            fw.push(u64_val(x, "firmware")?);
        }
        let fw_set: HashSet<u64> = fw.iter().copied().collect();
        if fw_set.len() != fw.len() {
            return Err("duplicate firmware versions".into());
        }
        let rules_v = rec["measurement_rules"]
            .as_array()
            .ok_or_else(|| "measurement_rules".to_string())?;
        let mut rules: HashMap<String, MeasurementRule> = HashMap::new();
        let mut selectors: HashSet<(u32, String, String)> = HashSet::new();
        for (j, rule) in rules_v.iter().enumerate() {
            expect_keys(
                rule,
                &[
                    "rule_id",
                    "kind",
                    "pcr_index",
                    "event_type",
                    "component",
                    "allowed_versions",
                    "allowed_digests",
                ],
                &format!("rule[{j}]"),
            )?;
            let rid = norm_id(&rule["rule_id"], "rule_id")?;
            if rules.contains_key(&rid) {
                return Err(format!("duplicate rule_id {rid}"));
            }
            let kind = rule["kind"]
                .as_str()
                .ok_or_else(|| "rule kind".to_string())?;
            if kind != "required" && kind != "optional" && kind != "forbidden" {
                return Err("rule kind".into());
            }
            let pcr = u32_val(&rule["pcr_index"], "pcr_index")?;
            if !supported_pcr(pcr) {
                return Err("unsupported pcr in rule".into());
            }
            let et = norm_id(&rule["event_type"], "event_type")?;
            let comp = norm_id(&rule["component"], "component")?;
            let sel = (pcr, et.clone(), comp.clone());
            if !selectors.insert(sel) {
                return Err("duplicate measurement rule selector".into());
            }
            let vers = &rule["allowed_versions"];
            let digs = &rule["allowed_digests"];
            if !vers.is_array() || !digs.is_array() {
                return Err("allow lists must be arrays".into());
            }
            let (versions, digests) = if kind == "forbidden" {
                if !vers.as_array().unwrap().is_empty() || !digs.as_array().unwrap().is_empty() {
                    return Err("forbidden rule arrays must be empty".into());
                }
                (Vec::new(), Vec::new())
            } else {
                let versions = sorted_unique_strs(vers, "allowed_versions")?;
                if versions.is_empty() {
                    return Err("allowed_versions nonempty required".into());
                }
                let digs_arr = digs.as_array().unwrap();
                let mut digests = Vec::new();
                let mut seen_d = HashSet::new();
                for d in digs_arr {
                    let d = d
                        .as_str()
                        .ok_or_else(|| "digest must be string".to_string())?;
                    require_exact_lower_hex(d, 32).map_err(map_hex_err)?;
                    if !seen_d.insert(d.to_string()) {
                        return Err("duplicate digest".into());
                    }
                    digests.push(d.to_string());
                }
                digests.sort();
                if digests.is_empty() {
                    return Err("allowed_digests nonempty required".into());
                }
                (versions, digests)
            };
            rules.insert(
                rid.clone(),
                MeasurementRule {
                    rule_id: rid,
                    kind: kind.to_string(),
                    pcr_index: pcr,
                    event_type: et,
                    component: comp,
                    allowed_versions: versions,
                    allowed_digests: digests,
                },
            );
        }
        let cons_v = rec["order_constraints"]
            .as_array()
            .ok_or_else(|| "order_constraints".to_string())?;
        let mut constraints = Vec::new();
        let mut seen_c: HashSet<(String, String)> = HashSet::new();
        let mut edges: Vec<(String, String)> = Vec::new();
        for c in cons_v {
            expect_keys(c, &["before_rule_id", "after_rule_id"], "order_constraint")?;
            let b = norm_id(&c["before_rule_id"], "before_rule_id")?;
            let a = norm_id(&c["after_rule_id"], "after_rule_id")?;
            if !rules.contains_key(&b) || !rules.contains_key(&a) {
                return Err("unknown order-constraint rule".into());
            }
            if b == a {
                return Err("self order constraint".into());
            }
            if rules[&b].kind == "forbidden" || rules[&a].kind == "forbidden" {
                return Err("order constraint on forbidden rule".into());
            }
            let key = (b.clone(), a.clone());
            if !seen_c.insert(key.clone()) {
                return Err("duplicate order constraint".into());
            }
            edges.push(key);
            constraints.push(OrderConstraint {
                before_rule_id: b,
                after_rule_id: a,
            });
        }
        if has_cycle(&edges) {
            return Err("cyclic order constraints".into());
        }
        policies.insert(
            pid.clone(),
            Policy {
                policy_id: pid,
                allowed_device_classes: classes,
                required_pcrs: req_pcrs,
                allowed_firmware_versions: fw,
                require_safe,
                unknown_event_mode: mode.to_string(),
                measurement_rules: rules,
                order_constraints: constraints,
            },
        );
    }

    let logs_raw = jload(data_dir, "event_logs.json")?;
    let logs_arr = logs_raw
        .as_array()
        .ok_or_else(|| "event_logs.json must be array".to_string())?;
    if logs_arr.len() as u32 > limits.maximum_event_logs {
        return Err("maximum_event_logs exceeded".into());
    }
    let mut event_logs: HashMap<String, EventLog> = HashMap::new();
    let mut total_events: u32 = 0;
    for (i, rec) in logs_arr.iter().enumerate() {
        expect_keys(
            rec,
            &["event_log_id", "device_id", "events"],
            &format!("event_logs[{i}]"),
        )?;
        let lid = norm_id(&rec["event_log_id"], "event_log_id")?;
        if event_logs.contains_key(&lid) {
            return Err(format!("duplicate event_log_id {lid}"));
        }
        let did = norm_id(&rec["device_id"], "device_id")?;
        if !devices.contains_key(&did) {
            return Err(format!("unknown device in event log {lid}"));
        }
        let events_v = rec["events"]
            .as_array()
            .ok_or_else(|| "events must be array".to_string())?;
        if events_v.len() as u32 > limits.maximum_events_per_log {
            return Err("maximum_events_per_log exceeded".into());
        }
        let mut events = Vec::new();
        let mut seqs: HashSet<u32> = HashSet::new();
        for (j, ev) in events_v.iter().enumerate() {
            expect_keys(
                ev,
                &[
                    "event_seq",
                    "pcr_index",
                    "event_type",
                    "component",
                    "version",
                    "measurement_digest",
                ],
                &format!("event[{j}]"),
            )?;
            let seq = u32_val(&ev["event_seq"], "event_seq")?;
            if !seqs.insert(seq) {
                return Err("duplicate event_seq".into());
            }
            let pcr = u32_val(&ev["pcr_index"], "pcr_index")?;
            if !supported_pcr(pcr) {
                return Err("unsupported PCR index in event".into());
            }
            let ver = ev["version"]
                .as_str()
                .ok_or_else(|| "version nonempty".to_string())?;
            if ver.is_empty() {
                return Err("version nonempty".into());
            }
            let digest = ev["measurement_digest"]
                .as_str()
                .ok_or_else(|| "measurement_digest must be string".to_string())?;
            require_exact_lower_hex(digest, 32).map_err(map_hex_err)?;
            events.push(Event {
                event_seq: seq,
                pcr_index: pcr,
                event_type: norm_id(&ev["event_type"], "event_type")?,
                component: norm_id(&ev["component"], "component")?,
                version: ver.to_string(),
                measurement_digest: digest.to_string(),
            });
            total_events += 1;
            if total_events > limits.maximum_total_events {
                return Err("maximum_total_events exceeded".into());
            }
        }
        event_logs.insert(
            lid.clone(),
            EventLog {
                event_log_id: lid,
                device_id: did,
                events,
            },
        );
    }

    let nonces_raw = jload(data_dir, "nonce_challenges.json")?;
    let nonces_arr = nonces_raw
        .as_array()
        .ok_or_else(|| "nonce_challenges.json must be array".to_string())?;
    if nonces_arr.len() as u32 > limits.maximum_nonce_challenges {
        return Err("maximum_nonce_challenges exceeded".into());
    }
    let mut nonces: HashMap<String, Nonce> = HashMap::new();
    for (i, rec) in nonces_arr.iter().enumerate() {
        expect_keys(
            rec,
            &[
                "nonce_id",
                "device_id",
                "nonce_hex",
                "issued_at",
                "expires_at",
                "initially_consumed_by_request_id_or_null",
            ],
            &format!("nonces[{i}]"),
        )?;
        let nid = norm_id(&rec["nonce_id"], "nonce_id")?;
        if nonces.contains_key(&nid) {
            return Err(format!("duplicate nonce_id {nid}"));
        }
        let did = norm_id(&rec["device_id"], "device_id")?;
        if !devices.contains_key(&did) {
            return Err(format!("unknown device in nonce {nid}"));
        }
        let nonce_hex = rec["nonce_hex"]
            .as_str()
            .ok_or_else(|| "nonce_hex must be string".to_string())?;
        require_exact_lower_hex(nonce_hex, 32).map_err(map_hex_err)?;
        let issued = u64_val(&rec["issued_at"], "issued_at")?;
        let expires = u64_val(&rec["expires_at"], "expires_at")?;
        if issued > expires {
            return Err("issued_at > expires_at".into());
        }
        let init = match &rec["initially_consumed_by_request_id_or_null"] {
            Value::Null => None,
            Value::String(s) => {
                let s = s.trim();
                if s.is_empty() {
                    return Err("initially_consumed invalid".into());
                }
                Some(s.to_string())
            }
            _ => return Err("initially_consumed invalid".into()),
        };
        nonces.insert(
            nid.clone(),
            Nonce {
                nonce_id: nid,
                device_id: did,
                nonce_hex: nonce_hex.to_string(),
                nonce_bytes: decode_lower_hex(nonce_hex)?,
                issued_at: issued,
                expires_at: expires,
                initially_consumed_by_request_id_or_null: init,
            },
        );
    }

    let ndjson_path = data_dir.join("quote_requests.ndjson");
    let text = fs::read_to_string(&ndjson_path)
        .map_err(|e| format!("unreadable NDJSON: {e}"))?;
    let mut requests = Vec::new();
    let mut seen_rid: HashSet<String> = HashSet::new();
    for (line_no, line) in text.lines().enumerate() {
        let line_no = line_no + 1;
        if line.trim().is_empty() {
            continue;
        }
        let rec: Value = serde_json::from_str(line)
            .map_err(|e| format!("bad NDJSON line {line_no}: {e}"))?;
        expect_keys(
            &rec,
            &[
                "request_id",
                "received_at",
                "device_id",
                "attestation_key_id",
                "nonce_id",
                "policy_id",
                "event_log_id",
                "quote_hex",
                "signature_hex",
            ],
            &format!("request line {line_no}"),
        )?;
        let rid = norm_id(&rec["request_id"], "request_id")?;
        if !seen_rid.insert(rid.clone()) {
            return Err(format!("duplicate request_id {rid}"));
        }
        let qh = rec["quote_hex"]
            .as_str()
            .ok_or_else(|| "quote/signature hex must be strings".to_string())?;
        let sh = rec["signature_hex"]
            .as_str()
            .ok_or_else(|| "quote/signature hex must be strings".to_string())?;
        let qb = decode_lower_hex(qh)
            .map_err(|e| format!("malformed request hex {rid}: {e}"))?;
        let sb = decode_lower_hex(sh)
            .map_err(|e| format!("malformed request hex {rid}: {e}"))?;
        if qb.len() as u32 > limits.maximum_quote_bytes {
            return Err("maximum_quote_bytes exceeded".into());
        }
        if sb.len() as u32 > limits.maximum_signature_bytes {
            return Err("maximum_signature_bytes exceeded".into());
        }
        requests.push(Request {
            request_id: rid,
            received_at: u64_val(&rec["received_at"], "received_at")?,
            device_id: norm_id(&rec["device_id"], "device_id")?,
            attestation_key_id: norm_id(&rec["attestation_key_id"], "attestation_key_id")?,
            nonce_id: norm_id(&rec["nonce_id"], "nonce_id")?,
            policy_id: norm_id(&rec["policy_id"], "policy_id")?,
            event_log_id: norm_id(&rec["event_log_id"], "event_log_id")?,
            quote_hex: qh.to_string(),
            signature_hex: sh.to_string(),
            quote_bytes: qb,
            signature_bytes: sb,
        });
    }
    if requests.len() as u32 > limits.maximum_requests {
        return Err("maximum_requests exceeded".into());
    }

    Ok(Dataset {
        devices,
        keys,
        policies,
        event_logs,
        nonces,
        requests,
        policy_limits: limits,
    })
}

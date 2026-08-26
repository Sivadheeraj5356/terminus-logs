//! Sealed bootorder loading and grammar checks.
use std::collections::BTreeMap;
use std::fs;

use crate::bootyard_boundary;
use crate::logical_seal;
use crate::reconcile_failure;
use crate::yard_inventory::Yard;

#[derive(Clone, Debug)]
pub struct Order {
    pub root: String,
    pub order_id: String,
    pub expected_generation: u64,
    pub next_generation: u64,
    pub final_target: String,
    pub job_mode: String,
    pub intents: Vec<Intent>,
    pub presets: Vec<(String, String)>,
    pub acceptance: Vec<AcceptJob>,
    pub target_members: Vec<String>,
    pub access_triggers: Vec<String>,
    pub seal: String,
    pub record: BTreeMap<String, String>,
}

#[derive(Clone, Debug)]
pub struct Intent {
    pub seq: u32,
    pub op: String,
    pub unit: String,
    pub instance: Option<String>,
    pub prestate: String,
    pub payload_digest: Option<String>,
    pub expected_class: String,
    pub payload_fields: Option<String>,
}

#[derive(Clone, Debug)]
pub struct AcceptJob {
    pub unit: String,
    pub outcome: String,
    pub reason: String,
}

pub fn load_order(root: &str, yard: &Yard) -> Result<Order, i32> {
    let record_raw = read(root, "order.record")?;
    let intent_raw = read(root, "unit.intent")?;
    let preset_raw = read(root, "preset.selection")?;
    let accept_raw = read(root, "acceptance.jobs")?;
    let seal_raw = read(root, "order.seal")?;
    let record = parse_kv(&record_raw)?;
    let order_id = req(&record, "order_id")?;
    let expected_generation: u64 = req(&record, "expected_generation")?.parse().map_err(|_| e(reconcile_failure::EXIT_ORDER_GRAMMAR, "gen"))?;
    let next_generation: u64 = req(&record, "next_generation")?.parse().map_err(|_| e(reconcile_failure::EXIT_ORDER_GRAMMAR, "ngen"))?;
    if next_generation != expected_generation + 1 {
        return Err(e(reconcile_failure::EXIT_ORDER_GRAMMAR, "generation step"));
    }
    if req(&record, "yard_host_label")? != yard.host_label || req(&record, "yard_machine_id")? != yard.machine_id {
        return Err(e(reconcile_failure::EXIT_ORDER_GRAMMAR, "yard identity mismatch"));
    }
    let final_target = req(&record, "final_target")?;
    let job_mode = req(&record, "job_mode")?;
    let members_digest = req(&record, "members_digest")?;
    let joined = format!("{}\n{}\n{}\n{}", intent_raw, preset_raw, accept_raw, seal_raw);
    // digest of other members in fixed order with their filenames
    // Members are concatenated as name LF content with content already LF-terminated.
    let blob = format!(
        "unit.intent\n{}preset.selection\n{}acceptance.jobs\n{}order.seal\n{}",
        intent_raw, preset_raw, accept_raw, seal_raw
    );
    let got = logical_seal::sha256_hex(blob.as_bytes());
    if got != members_digest {
        let _ = joined;
        return Err(e(reconcile_failure::EXIT_ORDER_GRAMMAR, "members digest"));
    }
    let seal = seal_raw.trim().to_string();
    let intents = parse_intents(&intent_raw)?;
    let presets = parse_presets(&preset_raw)?;
    let (acceptance, target_members, access_triggers) = parse_accept(&accept_raw)?;
    Ok(Order {
        root: root.to_string(),
        order_id,
        expected_generation,
        next_generation,
        final_target,
        job_mode,
        intents,
        presets,
        acceptance,
        target_members,
        access_triggers,
        seal,
        record,
    })
}

fn parse_intents(raw: &str) -> Result<Vec<Intent>, i32> {
    let mut out = Vec::new();
    for line in raw.lines() {
        if line.is_empty() { continue; }
        let p: Vec<&str> = line.split('\t').collect();
        if p.len() != 8 {
            return Err(e(reconcile_failure::EXIT_ORDER_GRAMMAR, "intent arity"));
        }
        out.push(Intent {
            seq: p[0].parse().map_err(|_| e(reconcile_failure::EXIT_ORDER_GRAMMAR, "seq"))?,
            op: p[1].into(),
            unit: p[2].into(),
            instance: if p[3] == "-" { None } else { Some(p[3].into()) },
            prestate: p[4].into(),
            payload_digest: if p[5] == "-" { None } else { Some(p[5].into()) },
            expected_class: p[6].into(),
            payload_fields: if p[7] == "-" { None } else { Some(p[7].into()) },
        });
    }
    Ok(out)
}

fn parse_presets(raw: &str) -> Result<Vec<(String, String)>, i32> {
    let mut out = Vec::new();
    for line in raw.lines() {
        if line.is_empty() { continue; }
        let mut sp = line.splitn(2, ' ');
        let act = sp.next().unwrap_or("");
        let pat = sp.next().unwrap_or("");
        if !matches!(act, "enable" | "disable" | "ignore") || pat.is_empty() {
            return Err(e(reconcile_failure::EXIT_ORDER_GRAMMAR, "preset line"));
        }
        out.push((act.into(), pat.into()));
    }
    Ok(out)
}

fn parse_accept(raw: &str) -> Result<(Vec<AcceptJob>, Vec<String>, Vec<String>), i32> {
    let mut jobs = Vec::new();
    let mut members = Vec::new();
    let mut triggers = Vec::new();
    for line in raw.lines() {
        if line.is_empty() { continue; }
        if let Some(rest) = line.strip_prefix("target_member=") {
            members.push(rest.to_string());
            continue;
        }
        if let Some(rest) = line.strip_prefix("access_trigger=") {
            triggers.push(rest.to_string());
            continue;
        }
        let p: Vec<&str> = line.split('\t').collect();
        if p.len() != 3 {
            return Err(e(reconcile_failure::EXIT_ORDER_GRAMMAR, "accept arity"));
        }
        jobs.push(AcceptJob { unit: p[0].into(), outcome: p[1].into(), reason: p[2].into() });
    }
    Ok((jobs, members, triggers))
}

fn parse_kv(raw: &str) -> Result<BTreeMap<String, String>, i32> {
    let mut m = BTreeMap::new();
    for line in raw.lines() {
        if line.is_empty() { continue; }
        let (k, v) = line.split_once('=').ok_or_else(|| e(reconcile_failure::EXIT_ORDER_GRAMMAR, "record"))?;
        m.insert(k.into(), v.into());
    }
    Ok(m)
}
fn req(m: &BTreeMap<String, String>, k: &str) -> Result<String, i32> {
    m.get(k).cloned().ok_or_else(|| e(reconcile_failure::EXIT_ORDER_GRAMMAR, "missing key"))
}
fn read(root: &str, name: &str) -> Result<String, i32> {
    fs::read_to_string(bootyard_boundary::logical_join(root, name))
        .map_err(|_| e(reconcile_failure::EXIT_ORDER_GRAMMAR, "missing order member"))
}
fn e(code: i32, msg: &str) -> i32 {
    crate::diagnostic_surface::emit_error(code, msg);
    code
}

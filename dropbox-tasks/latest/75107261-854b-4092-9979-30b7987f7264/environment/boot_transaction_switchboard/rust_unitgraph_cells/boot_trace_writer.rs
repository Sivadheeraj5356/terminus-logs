//! Deterministic boot.trace rendering.
use crate::boot_target_simulator::SimResult;
use crate::fragment_locator::EffectiveUnit;
use crate::logical_seal;
use crate::yard_inventory::Yard;
use std::collections::BTreeMap;

pub fn render(
    jobs: &SimResult,
    effective: &BTreeMap<String, EffectiveUnit>,
    yard: &Yard,
) -> Result<String, i32> {
    let mut lines = Vec::new();
    for (i, ev) in jobs.events.iter().enumerate() {
        let parts: Vec<&str> = ev.split('\t').collect();
        let unit = parts.get(1).copied().unwrap_or("");
        let digest = effective
            .get(unit)
            .map(|e| logical_seal::sha256_hex(e.fragment_logical.as_bytes()))
            .unwrap_or_else(|| logical_seal::sha256_hex(b"-"));
        lines.push(format!("{}\t{}\t{}\t{}", i, ev, digest, yard.machine_id));
    }
    for (u, st) in &jobs.states {
        lines.push(format!("state\t{}\t{}\t{}", u, st.state.as_str(), st.reason));
    }
    lines.sort();
    // keep event order for event lines — rewrite: events first in order, then states sorted
    let mut out = Vec::new();
    for (i, ev) in jobs.events.iter().enumerate() {
        let parts: Vec<&str> = ev.split('\t').collect();
        let unit = parts.get(1).copied().unwrap_or("");
        let digest = effective
            .get(unit)
            .map(|e| logical_seal::sha256_hex(e.fragment_logical.as_bytes()))
            .unwrap_or_else(|| logical_seal::sha256_hex(b"-"));
        out.push(format!("step\t{}\t{}\t{}", i, ev, digest));
    }
    let mut states: Vec<_> = jobs.states.values().map(|s| format!("state\t{}\t{}\t{}", s.unit, s.state.as_str(), s.reason)).collect();
    states.sort();
    out.extend(states);
    Ok(out.join("\n") + "\n")
}

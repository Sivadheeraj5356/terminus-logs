//! Device alias identity deduplication.
use std::collections::BTreeMap;

use crate::boot_semantics::Semantics;
use crate::yard_inventory::Yard;

pub fn resolve_what(what: &str, yard: &Yard, sem: &Semantics) -> Option<(String, bool)> {
    // returns (device_unit, ready)
    let mode = sem.decide_or("DEVICE_DEDUP", &["mode"], "alias_spelling");
    if let Some(dev) = yard.devices.get(what) {
        return Some((what.to_string(), dev.ready));
    }
    if let Some(unit) = yard.alias_to_device.get(what) {
        if let Some(dev) = yard.devices.get(unit) {
            if mode == "alias_spelling" {
                return Some((what.to_string(), dev.ready));
            }
            // dedupe by backing: pick canonical unit with that backing
            let backing = &dev.backing;
            for (u, d) in &yard.devices {
                if &d.backing == backing {
                    return Some((u.clone(), d.ready));
                }
            }
        }
    }
    // try uuid:/label:/dev: forms already in alias map
    None
}

pub fn backing_groups(yard: &Yard) -> BTreeMap<String, Vec<String>> {
    let mut m: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for (u, d) in &yard.devices {
        m.entry(d.backing.clone()).or_default().push(u.clone());
    }
    for v in m.values_mut() { v.sort(); }
    m
}

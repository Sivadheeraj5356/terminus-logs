//! Alias chains, masks, and enablement classification.
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

use crate::boot_semantics::Semantics;
use crate::bootyard_boundary;
use crate::order_reader::Order;
use crate::reconcile_failure;
use crate::fragment_locator::EffectiveUnit;

#[derive(Clone, Debug)]
pub struct EnablementState {
    pub classes: BTreeMap<String, String>,
    pub evidence: Vec<String>,
}

pub fn resolve_alias_chain(yard: &str, name: &str, sem: &Semantics) -> Result<(String, bool), i32> {
    let depth_mode = sem.decide_or("ALIAS_DEPTH", &["mode"], "single_hop");
    let tiers = ["etc/systemd/system", "run/systemd/system", "usr/lib/systemd/system"];
    let mut cur = name.to_string();
    let mut seen = BTreeSet::new();
    let mut hops = 0;
    loop {
        if !seen.insert(cur.clone()) {
            return Err(e("alias loop"));
        }
        hops += 1;
        if depth_mode == "single_hop" && hops > 1 {
            return Ok((cur, false));
        }
        let mut found_link = None;
        let mut found_file = None;
        let mut masked = false;
        for tier in &tiers {
            let p = bootyard_boundary::logical_join(yard, &format!("{}/{}", tier, cur));
            let path = Path::new(&p);
            if !path.exists() && fs::symlink_metadata(path).is_err() { continue; }
            let meta = fs::symlink_metadata(path).map_err(|_| e("alias meta"))?;
            if meta.file_type().is_symlink() {
                let t = fs::read_link(path).map_err(|_| e("alias read"))?;
                let ts = t.to_string_lossy().to_string();
                if ts == "/dev/null" {
                    masked = true;
                    found_link = Some(ts);
                    break;
                }
                found_link = Some(ts);
                break;
            } else if meta.file_type().is_file() {
                found_file = Some(cur.clone());
                break;
            }
        }
        if masked {
            return Ok((cur, true));
        }
        if let Some(t) = found_link {
            // relative alias to another unit name
            let base = Path::new(&t).file_name().map(|x| x.to_string_lossy().to_string()).unwrap_or(t);
            cur = base;
            continue;
        }
        if found_file.is_some() {
            return Ok((cur, false));
        }
        return Ok((cur, false));
    }
}

pub fn classify_enablement(
    yard_root: &str,
    effective: &BTreeMap<String, EffectiveUnit>,
    order: &Order,
    _sem: &Semantics,
) -> Result<EnablementState, i32> {
    let admin = bootyard_boundary::logical_join(yard_root, "etc/systemd/system");
    let mut classes = BTreeMap::new();
    let mut evidence = Vec::new();
    for (unit, eu) in effective {
        if eu.masked {
            classes.insert(unit.clone(), "masked".into());
            evidence.push(format!("{}\tmasked\t/dev/null", unit));
            continue;
        }
        let mut enabled = false;
        // scan wants/requires
        if Path::new(&admin).is_dir() {
            for ent in fs::read_dir(&admin).map_err(|_| e("admin"))? {
                let ent = ent.map_err(|_| e("admin"))?;
                let name = ent.file_name().to_string_lossy().to_string();
                if name.ends_with(".wants") || name.ends_with(".requires") {
                    let link = ent.path().join(unit);
                    if link.exists() || fs::symlink_metadata(&link).is_ok() {
                        enabled = true;
                        evidence.push(format!("{}\tenabled\t{}/{}", unit, name, unit));
                    }
                }
            }
        }
        let class = if enabled {
            "enabled"
        } else if eu.parsed.sections.get("Install").map(|s| !s.is_empty()).unwrap_or(false) {
            "disabled"
        } else {
            "static"
        };
        classes.insert(unit.clone(), class.into());
    }
    let _ = order;
    Ok(EnablementState { classes, evidence })
}

fn e(msg: &str) -> i32 {
    crate::diagnostic_surface::emit_error(reconcile_failure::EXIT_UNIT_LOADING, msg);
    reconcile_failure::EXIT_UNIT_LOADING
}

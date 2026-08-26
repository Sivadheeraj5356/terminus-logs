use std::collections::{BTreeMap, HashMap, HashSet};

use crate::types::{ParsedLine, TrayCfg, TrayState};

pub fn apply_event(
    trays: &mut BTreeMap<String, TrayState>,
    cfg: &HashMap<String, TrayCfg>,
    line: &ParsedLine,
    accepted: &HashSet<String>,
) -> Result<(), String> {
    if line.event_id.is_empty() {
        return Err("BAD_EVENT".into());
    }
    if accepted.contains(&line.event_id) {
        return Err("DUPLICATE_EVENT".into());
    }
    let op = line.op.as_str();
    match op {
        "LOAD" | "UNLOAD" | "REGEN" | "SEAL" | "OPEN" | "LOCK" | "UNLOCK" | "HOLD" | "RELEASE" => {}
        _ => return Err("UNKNOWN_OP".into()),
    }
    if !cfg.contains_key(&line.tray_id) {
        return Err("UNKNOWN_TRAY".into());
    }
    if !field_profile_ok(line) {
        return Err("BAD_LINE".into());
    }
    {
        let st_ref = trays.get(&line.tray_id).unwrap();
        if st_ref.locked && op != "LOCK" && op != "UNLOCK" {
            return Err("TRAY_LOCKED".into());
        }
        if st_ref.held && matches!(op, "LOAD" | "UNLOAD" | "REGEN" | "SEAL" | "OPEN") {
            return Err("TRAY_HELD".into());
        }
        if op == "REGEN" {
            let my_tier = cfg.get(&line.tray_id).unwrap().tier;
            for (name, other) in trays.iter() {
                let other_tier = cfg.get(name).unwrap().tier;
                if other_tier < my_tier && other.units > 0 {
                    return Err("REGEN_BLOCKED".into());
                }
            }
        }
    }
    let st = trays.get_mut(&line.tray_id).unwrap();
    match op {
        "LOCK" => lock(st),
        "UNLOCK" => unlock(st),
        "HOLD" => hold(st),
        "RELEASE" => release(st),
        "LOAD" => load(st, line),
        "UNLOAD" => unload(st, line),
        "REGEN" => regen(st),
        "SEAL" => seal(st),
        "OPEN" => open(st),
        _ => Err("UNKNOWN_OP".into()),
    }
}

fn field_profile_ok(line: &ParsedLine) -> bool {
    let units_empty = line.units_raw.is_empty();
    let lot_empty = line.lot_raw.is_empty();
    match line.op.as_str() {
        "LOAD" | "UNLOAD" => !units_empty && lot_empty,
        "REGEN" | "SEAL" | "OPEN" | "LOCK" | "UNLOCK" | "HOLD" | "RELEASE" => {
            units_empty && lot_empty
        }
        _ => true,
    }
}

fn lock(st: &mut TrayState) -> Result<(), String> {
    st.locked = true;
    Ok(())
}

fn unlock(st: &mut TrayState) -> Result<(), String> {
    if !st.locked {
        return Err("BAD_STATE".into());
    }
    st.locked = false;
    Ok(())
}

fn hold(st: &mut TrayState) -> Result<(), String> {
    if st.held {
        return Err("BAD_STATE".into());
    }
    st.held = true;
    Ok(())
}

fn release(st: &mut TrayState) -> Result<(), String> {
    if !st.held {
        return Err("BAD_STATE".into());
    }
    st.held = false;
    Ok(())
}

fn load(st: &mut TrayState, line: &ParsedLine) -> Result<(), String> {
    let units: i64 = line.units_raw.parse().map_err(|_| "BAD_UNITS".to_string())?;
    if units <= 0 {
        return Err("BAD_UNITS".into());
    }
    if st.units + units > st.capacity_units {
        return Err("OVER_CAPACITY".into());
    }
    st.units += units;
    st.cycles_since_regen += 1;
    Ok(())
}

fn unload(st: &mut TrayState, line: &ParsedLine) -> Result<(), String> {
    let units: i64 = line.units_raw.parse().map_err(|_| "BAD_UNITS".to_string())?;
    if units <= 0 {
        return Err("BAD_UNITS".into());
    }
    if st.units == 0 {
        return Err("EMPTY_TRAY".into());
    }
    if units > st.units {
        return Err("UNDERFLOW".into());
    }
    st.units -= units;
    Ok(())
}

fn regen(st: &mut TrayState) -> Result<(), String> {
    st.units = 0;
    st.sealed = false;
    st.cycles_since_regen = 0;
    Ok(())
}

fn seal(st: &mut TrayState) -> Result<(), String> {
    if st.sealed {
        return Err("BAD_STATE".into());
    }
    if st.units <= 0 {
        return Err("BAD_STATE".into());
    }
    st.sealed = true;
    Ok(())
}

fn open(st: &mut TrayState) -> Result<(), String> {
    if !st.sealed {
        return Err("BAD_STATE".into());
    }
    st.sealed = false;
    Ok(())
}

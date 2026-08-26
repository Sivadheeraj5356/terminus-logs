use crate::hex::in_bounds;
use crate::model::{Scenario, UnitIn};

pub fn invalid_reason(scenario: &Scenario) -> Option<&'static str> {
    let mut sorted = scenario.units.clone();
    sorted.sort_by(|a, b| a.id.cmp(&b.id));
    if let Some(r) = check_overlap(&sorted) {
        return Some(r);
    }
    for u in &sorted {
        if let Some(r) = check_placement(&scenario.map.width, &scenario.map.height, &scenario.map.blocked, u) {
            return Some(r);
        }
    }
    None
}

fn check_overlap(units: &[UnitIn]) -> Option<&'static str> {
    for i in 0..units.len() {
        for j in (i + 1)..units.len() {
            if units[i].hex == units[j].hex {
                return Some("OVERLAP");
            }
        }
    }
    None
}

fn check_placement(
    width: &i32,
    height: &i32,
    blocked: &[Vec<bool>],
    u: &UnitIn,
) -> Option<&'static str> {
    if !in_bounds(*width, *height, u.hex[0], u.hex[1]) {
        return Some("OOB");
    }
    if blocked[u.hex[1] as usize][u.hex[0] as usize] {
        return Some("BLOCKED");
    }
    None
}

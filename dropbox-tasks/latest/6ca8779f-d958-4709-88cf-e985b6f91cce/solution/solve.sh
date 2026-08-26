#!/bin/bash
set -euo pipefail

src_dir="/app/environment/skirmish/src"

cat > "$src_dir/hex.rs" <<'EOF'
/// Axial-style grid helpers used by movement and ranging.

pub fn neighbors(x: i32, y: i32) -> [[i32; 2]; 6] {
    [
        [x + 1, y],
        [x - 1, y],
        [x, y + 1],
        [x, y - 1],
        [x + 1, y - 1],
        [x - 1, y + 1],
    ]
}

pub fn in_bounds(width: i32, height: i32, x: i32, y: i32) -> bool {
    x >= 0 && y >= 0 && x < width && y < height
}

pub fn distance(a: [i32; 2], b: [i32; 2]) -> i32 {
    cube_distance(a, b)
}

/// Inclusive line of hex cells from a to b (stable for determinism).
pub fn hex_line(a: [i32; 2], b: [i32; 2]) -> Vec<[i32; 2]> {
    let n = cube_distance(a, b).max(1);
    let mut out = Vec::with_capacity((n + 1) as usize);
    for i in 0..=n {
        let t = i as f64 / n as f64;
        let x = (a[0] as f64 + (b[0] - a[0]) as f64 * t).round() as i32;
        let y = (a[1] as f64 + (b[1] - a[1]) as f64 * t).round() as i32;
        if out.last().copied() != Some([x, y]) {
            out.push([x, y]);
        }
    }
    if out.last().copied() != Some(b) {
        out.push(b);
    }
    out
}

pub fn cube_distance(a: [i32; 2], b: [i32; 2]) -> i32 {
    let dx = (a[0] - b[0]).abs();
    let dy = (a[1] - b[1]).abs();
    let dz = ((a[0] + a[1]) - (b[0] + b[1])).abs();
    dx.max(dy).max(dz)
}
EOF

cat > "$src_dir/initiative.rs" <<'EOF'
use crate::model::Unit;

pub fn order(units: &[Unit]) -> Vec<String> {
    let mut ids: Vec<&Unit> = units.iter().collect();
    ids.sort_by(|a, b| b.speed.cmp(&a.speed).then_with(|| a.id.cmp(&b.id)));
    ids.into_iter().map(|u| u.id.clone()).collect()
}
EOF

cat > "$src_dir/combat.rs" <<'EOF'
use crate::constants::BASE_STRIKE;
use crate::traits_mod::has_trait;

pub fn strike_damage(attacker_traits: &[String], target_armor: i32) -> i32 {
    if has_trait(attacker_traits, "PIERCE") {
        BASE_STRIKE
    } else {
        (BASE_STRIKE - target_armor).max(1)
    }
}
EOF

cat > "$src_dir/morale.rs" <<'EOF'
use crate::constants::MORALE_HP;

pub fn breaks_after_hit(hp_after: i32) -> bool {
    hp_after > 0 && hp_after < MORALE_HP
}
EOF

cat > "$src_dir/beacon.rs" <<'EOF'
use crate::hex::distance;
use crate::model::BeaconIn;

pub fn covered_by_team(beacons: &[BeaconIn], team: &str, hex: [i32; 2]) -> bool {
    beacons
        .iter()
        .any(|b| b.team == team && distance(b.hex, hex) <= b.radius)
}
EOF

cat > "$src_dir/overwatch.rs" <<'EOF'
use crate::combat::strike_damage;
use crate::hex::distance;
use crate::los::has_los;
use crate::model::{BeaconIn, Event, Map, Unit};
use crate::traits_mod::has_trait;
use crate::vision::can_see;

pub fn collect_overwatch_ids(units: &[Unit], mover_id: &str, map: &Map, beacons: &[BeaconIn]) -> Vec<String> {
    let Some(mover) = units.iter().find(|u| u.id == mover_id && u.alive) else {
        return Vec::new();
    };
    let mut ids: Vec<String> = units
        .iter()
        .filter(|u| {
            u.alive
                && u.team != mover.team
                && has_trait(&u.traits, "OVERWATCH")
                && can_see(u, mover, beacons)
                && has_los(map, u.hex, mover.hex)
                && distance(u.hex, mover.hex) <= u.range
        })
        .map(|u| u.id.clone())
        .collect();
    ids.sort();
    ids
}

pub fn build_overwatch_event(seq: u32, actor: &str, target: &str, damage: i32) -> Event {
    Event {
        seq,
        kind: "OVERWATCH".to_string(),
        actor: Some(actor.to_string()),
        from: None,
        to: None,
        target: Some(target.to_string()),
        damage: Some(damage),
        detail: None,
    }
}

pub fn damage_for(attacker: &Unit, target: &Unit) -> i32 {
    strike_damage(&attacker.traits, target.armor)
}
EOF

cat > "$src_dir/validate.rs" <<'EOF'
use crate::hex::in_bounds;
use crate::model::{Scenario, UnitIn};

pub fn invalid_reason(scenario: &Scenario) -> Option<&'static str> {
    let mut sorted = scenario.units.clone();
    sorted.sort_by(|a, b| a.id.cmp(&b.id));
    for u in &sorted {
        if let Some(r) = check_placement(&scenario.map.width, &scenario.map.height, &scenario.map.blocked, u) {
            return Some(r);
        }
    }
    check_overlap(&sorted)
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
EOF

cat > "$src_dir/digest.rs" <<'EOF'
use crate::model::Event;
use serde_json::{Map, Value};
use sha2::{Digest, Sha256};

pub fn transcript_digest(events: &[Event]) -> String {
    let value = serde_json::to_value(events).unwrap_or(Value::Array(vec![]));
    let canonical = canonicalize(value);
    let raw = serde_json::to_string(&canonical).unwrap_or_else(|_| "[]".to_string());
    let mut h = Sha256::new();
    h.update(raw.as_bytes());
    format!("sha256:{:x}", h.finalize())
}

fn canonicalize(v: Value) -> Value {
    match v {
        Value::Object(map) => {
            let mut items: Vec<(String, Value)> = map.into_iter().collect();
            items.sort_by(|a, b| a.0.cmp(&b.0));
            let mut out = Map::new();
            for (k, val) in items {
                out.insert(k, canonicalize(val));
            }
            Value::Object(out)
        }
        Value::Array(arr) => Value::Array(arr.into_iter().map(canonicalize).collect()),
        other => other,
    }
}
EOF

chmod +x /app/bin/skirmish
cd /app/environment/skirmish
cargo build --release --locked

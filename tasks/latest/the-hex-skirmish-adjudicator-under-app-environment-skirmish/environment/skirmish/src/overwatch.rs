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
    ids.sort_by(|a, b| b.cmp(a));
    ids
}

pub fn build_overwatch_event(seq: u32, actor: &str, target: &str, damage: i32) -> Event {
    Event {
        seq,
        kind: "STRIKE".to_string(),
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

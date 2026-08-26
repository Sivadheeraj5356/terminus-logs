use crate::board::{can_stand, living_mut};
use crate::combat::strike_damage;
use crate::error::ErrMsg;
use crate::hex::{distance, neighbors};
use crate::initiative;
use crate::los::has_los;
use crate::model::{Event, Unit};
use crate::morale::breaks_after_hit;
use crate::overwatch::{build_overwatch_event, collect_overwatch_ids, damage_for};
use crate::parse::{load_scenario, to_units};
use crate::report::{invalid_report, resolved_report, write_report};
use crate::validate::invalid_reason;
use crate::vision::can_see;
use std::path::Path;

pub fn run_adjudicate(scenario_path: &Path, out_path: &Path) -> Result<u8, ErrMsg> {
    let scenario = load_scenario(scenario_path)?;
    if let Some(reason) = invalid_reason(&scenario) {
        let report = invalid_report(reason);
        write_report(out_path, &report)?;
        return Ok(2);
    }

    let mut units = to_units(&scenario);
    let map = scenario.map.clone();
    let beacons = scenario.beacons.clone();
    let order = initiative::order(&units);
    let mut events: Vec<Event> = Vec::new();
    let mut seq: u32 = 0;

    for actor_id in order.clone() {
        {
            let Some(actor) = living_mut(&mut units, &actor_id) else {
                continue;
            };
            if actor.actions_cancelled || actor.morale_broken {
                continue;
            }
            actor.armor = actor.base_armor;
        }

        push(
            &mut events,
            &mut seq,
            Event {
                seq: 0,
                kind: "TURN_START".to_string(),
                actor: Some(actor_id.clone()),
                from: None,
                to: None,
                target: None,
                damage: None,
                detail: None,
            },
        );

        let actions = {
            let Some(actor) = units.iter().find(|u| u.id == actor_id) else {
                continue;
            };
            actor.actions.clone()
        };

        for action in actions {
            if !still_active(&units, &actor_id) {
                break;
            }
            if let Some(rest) = action.strip_prefix("MOVE:") {
                resolve_move(
                    &mut units,
                    &map,
                    &beacons,
                    &actor_id,
                    rest,
                    &mut events,
                    &mut seq,
                );
            } else if action == "STRIKE" {
                resolve_strike(
                    &mut units,
                    &map,
                    &beacons,
                    &actor_id,
                    &mut events,
                    &mut seq,
                );
            } else if action == "GUARD" {
                resolve_guard(&mut units, &actor_id, &mut events, &mut seq);
            } else {
                push(
                    &mut events,
                    &mut seq,
                    Event {
                        seq: 0,
                        kind: "ACTION_FAIL".to_string(),
                        actor: Some(actor_id.clone()),
                        from: None,
                        to: None,
                        target: None,
                        damage: None,
                        detail: Some("UNKNOWN_ACTION".to_string()),
                    },
                );
            }
        }
    }

    let report = resolved_report(order, events, &units);
    write_report(out_path, &report)?;
    Ok(0)
}

fn still_active(units: &[Unit], id: &str) -> bool {
    units
        .iter()
        .any(|u| u.id == id && u.alive && !u.actions_cancelled && !u.morale_broken)
}

fn push(events: &mut Vec<Event>, seq: &mut u32, mut ev: Event) {
    ev.seq = *seq;
    *seq += 1;
    events.push(ev);
}

fn parse_xy(spec: &str) -> Option<[i32; 2]> {
    let mut parts = spec.split(',');
    let x = parts.next()?.parse().ok()?;
    let y = parts.next()?.parse().ok()?;
    if parts.next().is_some() {
        return None;
    }
    Some([x, y])
}

fn resolve_move(
    units: &mut Vec<Unit>,
    map: &crate::model::Map,
    beacons: &[crate::model::BeaconIn],
    actor_id: &str,
    dest_spec: &str,
    events: &mut Vec<Event>,
    seq: &mut u32,
) {
    let (from, dest_ok) = {
        let Some(actor) = units.iter().find(|u| u.id == actor_id && u.alive) else {
            return;
        };
        let from = actor.hex;
        let parsed = parse_xy(dest_spec);
        let ok = match parsed {
            Some(to) => {
                neighbors(from[0], from[1]).contains(&to) && can_stand(map, units, to, Some(actor_id))
            }
            None => false,
        };
        (from, parsed.filter(|_| ok))
    };
    let Some(to) = dest_ok else {
        push(
            events,
            seq,
            Event {
                seq: 0,
                kind: "ACTION_FAIL".to_string(),
                actor: Some(actor_id.to_string()),
                from: None,
                to: None,
                target: None,
                damage: None,
                detail: Some("ILLEGAL_MOVE".to_string()),
            },
        );
        return;
    };
    if let Some(actor) = living_mut(units, actor_id) {
        actor.hex = to;
    }
    push(
        events,
        seq,
        Event {
            seq: 0,
            kind: "MOVE".to_string(),
            actor: Some(actor_id.to_string()),
            from: Some(from),
            to: Some(to),
            target: None,
            damage: None,
            detail: None,
        },
    );
    apply_overwatch(units, map, beacons, actor_id, events, seq);
}

fn apply_overwatch(
    units: &mut Vec<Unit>,
    map: &crate::model::Map,
    beacons: &[crate::model::BeaconIn],
    mover_id: &str,
    events: &mut Vec<Event>,
    seq: &mut u32,
) {
    let ids = collect_overwatch_ids(units, mover_id, map, beacons);
    for ow_id in ids {
        if !units.iter().any(|u| u.id == mover_id && u.alive) {
            break;
        }
        let (dmg, _) = {
            let attacker = units.iter().find(|u| u.id == ow_id && u.alive).cloned();
            let target = units.iter().find(|u| u.id == mover_id && u.alive).cloned();
            match (attacker, target) {
                (Some(a), Some(t)) => (damage_for(&a, &t), true),
                _ => continue,
            }
        };
        push(
            events,
            seq,
            build_overwatch_event(*seq, &ow_id, mover_id, dmg),
        );
        apply_damage(units, mover_id, dmg, events, seq);
    }
}

fn resolve_strike(
    units: &mut Vec<Unit>,
    map: &crate::model::Map,
    beacons: &[crate::model::BeaconIn],
    actor_id: &str,
    events: &mut Vec<Event>,
    seq: &mut u32,
) {
    let choice = {
        let Some(actor) = units.iter().find(|u| u.id == actor_id && u.alive).cloned() else {
            return;
        };
        let mut candidates: Vec<&Unit> = units
            .iter()
            .filter(|u| {
                u.alive
                    && u.team != actor.team
                    && can_see(&actor, u, beacons)
                    && has_los(map, actor.hex, u.hex)
                    && distance(actor.hex, u.hex) <= actor.range
            })
            .collect();
        candidates.sort_by(|a, b| {
            distance(actor.hex, a.hex)
                .cmp(&distance(actor.hex, b.hex))
                .then_with(|| a.id.cmp(&b.id))
        });
        candidates.first().map(|u| {
            (
                u.id.clone(),
                strike_damage(&actor.traits, u.armor),
            )
        })
    };
    let Some((target_id, dmg)) = choice else {
        push(
            events,
            seq,
            Event {
                seq: 0,
                kind: "ACTION_FAIL".to_string(),
                actor: Some(actor_id.to_string()),
                from: None,
                to: None,
                target: None,
                damage: None,
                detail: Some("NO_TARGET".to_string()),
            },
        );
        return;
    };
    push(
        events,
        seq,
        Event {
            seq: 0,
            kind: "STRIKE".to_string(),
            actor: Some(actor_id.to_string()),
            from: None,
            to: None,
            target: Some(target_id.clone()),
            damage: Some(dmg),
            detail: None,
        },
    );
    apply_damage(units, &target_id, dmg, events, seq);
}

fn apply_damage(
    units: &mut Vec<Unit>,
    target_id: &str,
    dmg: i32,
    events: &mut Vec<Event>,
    seq: &mut u32,
) {
    let Some(t) = living_mut(units, target_id) else {
        return;
    };
    t.hp -= dmg;
    if t.hp <= 0 {
        t.alive = false;
        t.hp = 0;
        push(
            events,
            seq,
            Event {
                seq: 0,
                kind: "DOWNED".to_string(),
                actor: Some(target_id.to_string()),
                from: None,
                to: None,
                target: None,
                damage: None,
                detail: None,
            },
        );
        return;
    }
    if breaks_after_hit(t.hp) {
        t.morale_broken = true;
        t.actions_cancelled = true;
        push(
            events,
            seq,
            Event {
                seq: 0,
                kind: "MORALE_BREAK".to_string(),
                actor: Some(target_id.to_string()),
                from: None,
                to: None,
                target: None,
                damage: None,
                detail: None,
            },
        );
    }
}

fn resolve_guard(units: &mut Vec<Unit>, actor_id: &str, events: &mut Vec<Event>, seq: &mut u32) {
    if let Some(actor) = living_mut(units, actor_id) {
        actor.armor += 1;
    }
    push(
        events,
        seq,
        Event {
            seq: 0,
            kind: "GUARD".to_string(),
            actor: Some(actor_id.to_string()),
            from: None,
            to: None,
            target: None,
            damage: None,
            detail: None,
        },
    );
}

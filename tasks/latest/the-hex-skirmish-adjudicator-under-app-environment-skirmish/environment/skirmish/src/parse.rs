use crate::error::ErrMsg;
use crate::model::{Scenario, Unit};
use std::fs;
use std::path::Path;

pub fn load_scenario(path: &Path) -> Result<Scenario, ErrMsg> {
    let raw = fs::read_to_string(path).map_err(|e| ErrMsg(format!("read scenario: {e}")))?;
    serde_json::from_str(&raw).map_err(|e| ErrMsg(format!("parse scenario: {e}")))
}

pub fn to_units(scenario: &Scenario) -> Vec<Unit> {
    scenario
        .units
        .iter()
        .map(|u| Unit {
            id: u.id.clone(),
            team: u.team.clone(),
            hex: u.hex,
            hp: u.hp,
            base_armor: u.armor,
            armor: u.armor,
            speed: u.speed,
            vision: u.vision,
            range: u.range,
            traits: u.traits.clone(),
            actions: u.actions.clone(),
            alive: true,
            morale_broken: false,
            actions_cancelled: false,
        })
        .collect()
}

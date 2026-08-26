use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Deserialize)]
pub struct Scenario {
    pub map: Map,
    pub units: Vec<UnitIn>,
    #[serde(default)]
    pub beacons: Vec<BeaconIn>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Map {
    pub width: i32,
    pub height: i32,
    pub elevation: Vec<Vec<i32>>,
    pub blocked: Vec<Vec<bool>>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct UnitIn {
    pub id: String,
    pub team: String,
    pub hex: [i32; 2],
    pub hp: i32,
    pub armor: i32,
    pub speed: i32,
    pub vision: i32,
    pub range: i32,
    #[serde(default)]
    pub traits: Vec<String>,
    #[serde(default)]
    pub actions: Vec<String>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct BeaconIn {
    pub hex: [i32; 2],
    pub radius: i32,
    pub team: String,
}

#[derive(Debug, Clone)]
pub struct Unit {
    pub id: String,
    pub team: String,
    pub hex: [i32; 2],
    pub hp: i32,
    pub base_armor: i32,
    pub armor: i32,
    pub speed: i32,
    pub vision: i32,
    pub range: i32,
    pub traits: Vec<String>,
    pub actions: Vec<String>,
    pub alive: bool,
    pub morale_broken: bool,
    pub actions_cancelled: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct Event {
    pub seq: u32,
    pub kind: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub actor: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub from: Option<[i32; 2]>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub to: Option<[i32; 2]>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub target: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub damage: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub detail: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Survivor {
    pub id: String,
    pub hp: i32,
    pub hex: [i32; 2],
    pub armor: i32,
}

#[derive(Debug, Clone, Serialize)]
pub struct Report {
    pub schema_version: u32,
    pub status: String,
    pub invalid_reason: Option<String>,
    pub initiative: Vec<String>,
    pub events: Vec<Event>,
    pub survivors: Vec<Survivor>,
    pub transcript_digest: String,
}

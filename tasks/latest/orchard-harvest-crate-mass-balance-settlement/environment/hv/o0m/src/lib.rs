use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Deserialize)]
pub struct PickLine {
    pub kind: String,
    pub pick_id: String,
    pub zone: String,
    pub sequence: u64,
    pub gross_g: u64,
    pub tare_profile_id: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct TareLine {
    pub kind: String,
    pub tare_profile_id: String,
    pub zone: String,
    pub generation: u64,
    pub start_seq: u64,
    pub end_seq: u64,
    pub offset_g: i64,
    pub status: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SupersedeLine {
    pub kind: String,
    pub target_pick_id: String,
    pub generation: u64,
    pub action: String,
    #[serde(default)]
    pub gross_g: u64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SpoilageLine {
    pub kind: String,
    pub target_pick_id: String,
    pub generation: u64,
}

#[derive(Debug, Clone)]
pub struct FeedEvent {
    pub position: u64,
    pub pick: Option<PickLine>,
    pub tare: Option<TareLine>,
    pub supersede: Option<SupersedeLine>,
    pub spoilage: Option<SpoilageLine>,
}

#[derive(Debug, Clone)]
pub struct InputFeed {
    pub events: Vec<FeedEvent>,
    pub picks: Vec<PickLine>,
    pub tares: Vec<TareLine>,
    pub supersedes: Vec<SupersedeLine>,
    pub spoilages: Vec<SpoilageLine>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ZoneBalance {
    pub zone: String,
    pub grade_prime: u32,
    pub grade_standard: u32,
    pub grade_cull: u32,
    pub net_kept_g: u64,
    pub net_refused: u32,
    pub pick_marks: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct BalanceReport {
    pub zones: Vec<ZoneBalance>,
    pub balance_stamp: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SupersedeWinner {
    pub generation: u64,
    pub action: String,
    pub gross_g: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SpoilageWinner {
    pub generation: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ZoneCheckpoint {
    pub grade_prime: u32,
    pub grade_standard: u32,
    pub grade_cull: u32,
    pub net_kept_g: u64,
    pub net_refused: u32,
    pub pick_marks: Vec<String>,
    pub kept_rows: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReplayCheckpoint {
    pub input_identity: String,
    pub schema_generation: u32,
    pub last_event_position: u64,
    pub tare_lineage: String,
    pub zone_order: Vec<String>,
    pub zone_states: HashMap<String, ZoneCheckpoint>,
    pub supersede_winners: HashMap<String, SupersedeWinner>,
    pub spoilage_winners: HashMap<String, SpoilageWinner>,
    pub previous_stamp_seed: String,
}

pub const CAP_NET_G: u64 = 12000;
pub const PICK_MARK_CADENCE: u32 = 4;
pub const SCHEMA_GENERATION: u32 = 3;

pub fn is_pick_kind(kind: &str) -> bool {
    kind == "pick"
}

pub fn is_tare_kind(kind: &str) -> bool {
    kind == "tare"
}

pub fn is_supersede_kind(kind: &str) -> bool {
    kind == "supersede"
}

pub fn is_spoilage_kind(kind: &str) -> bool {
    kind == "spoilage"
}

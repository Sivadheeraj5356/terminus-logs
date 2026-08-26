#!/usr/bin/env bash
set -euo pipefail

log() { printf '[solve] %s\n' "$1"; }

log "repair zone label folding"
sed -i 's/let folded = raw.to_lowercase();/let folded = raw.to_string();/' /app/hv/o1p/src/lib.rs
sed -i 's/let trimmed = folded.trim();//' /app/hv/o1p/src/lib.rs
sed -i 's/trimmed.to_string()/folded/' /app/hv/o1p/src/lib.rs

log "repair grade band helpers"
sed -i 's/v > 200/v >= 200/' /app/hv/o2s/src/lib.rs
sed -i 's/v < 850/v <= 850/' /app/hv/o2s/src/lib.rs

log "repair tare registry"
cat > /app/hv/o6t/src/lib.rs <<'EOF'
use std::collections::HashMap;

use o0m::TareLine;

#[derive(Debug, Clone)]
pub struct TareRegistry {
    records: Vec<TareLine>,
}

impl TareRegistry {
    pub fn ingest(tares: &[TareLine]) -> Self {
        Self {
            records: tares.to_vec(),
        }
    }

    pub fn resolve_offset(&self, profile_id: &str, sequence: u64) -> i64 {
        let mut recs: Vec<&TareLine> = self
            .records
            .iter()
            .filter(|r| r.tare_profile_id == profile_id)
            .collect();
        recs.sort_by(|a, b| b.generation.cmp(&a.generation));
        for rec in recs {
            if rec.status != "active" {
                continue;
            }
            if rec.start_seq <= sequence && sequence < rec.end_seq {
                return rec.offset_g;
            }
        }
        0
    }

    pub fn lineage(&self) -> String {
        let mut by_id: HashMap<String, &TareLine> = HashMap::new();
        for rec in &self.records {
            let replace = match by_id.get(&rec.tare_profile_id) {
                None => true,
                Some(prev) => rec.generation > prev.generation,
            };
            if replace {
                by_id.insert(rec.tare_profile_id.clone(), rec);
            }
        }
        let mut ids: Vec<&String> = by_id.keys().collect();
        ids.sort();
        let mut parts = Vec::new();
        for id in ids {
            let rec = by_id[id];
            parts.push(format!(
                "{}|{}|{}|{}|{}|{}|{}",
                rec.tare_profile_id,
                rec.generation,
                rec.zone,
                rec.start_seq,
                rec.end_seq,
                rec.offset_g,
                rec.status
            ));
        }
        parts.join(";")
    }
}

pub fn effective_net_g(gross: u64, offset: i64) -> Option<u64> {
    if gross > i64::MAX as u64 {
        return None;
    }
    let signed = gross as i64;
    let sum = signed.checked_add(offset)?;
    if sum < 0 {
        return None;
    }
    Some(sum as u64)
}
EOF

log "repair supersede ledger"
sed -i 's/sup.generation.to_string() > prev.generation.to_string()/sup.generation > prev.generation/' /app/st/o7x/src/lib.rs

log "repair zone accumulation and replay"
cat > /app/st/o3z/src/lib.rs <<'EOF'
use std::collections::HashMap;

use o2s::{Grade, downgrade_grade, pick_grade};
use o4b::mix_pick_mark;
use o0m::{CAP_NET_G, PICK_MARK_CADENCE, ZoneBalance, ZoneCheckpoint};
use o7x::SettledPick;

#[derive(Default)]
struct Lane {
    grade_prime: u32,
    grade_standard: u32,
    grade_cull: u32,
    net_kept_g: u64,
    net_refused: u32,
    pick_marks: Vec<String>,
    kept_rows: u32,
}

pub struct ZoneTracker {
    order: Vec<String>,
    lanes: HashMap<String, Lane>,
}

impl Default for ZoneTracker {
    fn default() -> Self {
        Self {
            order: Vec::new(),
            lanes: HashMap::new(),
        }
    }
}

fn cap_exceeded(kept: u64, incoming: u64) -> bool {
    kept + incoming > CAP_NET_G
}

fn mark_cadence_hit(kept_rows: u32) -> bool {
    kept_rows % PICK_MARK_CADENCE == 0
}

fn record_refusal(lane: &mut Lane) {
    lane.net_refused += 1;
}

fn bump_grade(lane: &mut Lane, grade: Grade) {
    match grade {
        Grade::Prime => lane.grade_prime += 1,
        Grade::Standard => lane.grade_standard += 1,
        Grade::Cull => lane.grade_cull += 1,
    }
}

fn append_pick_mark(lane: &mut Lane, zone: &str) {
    let mark_idx = lane.pick_marks.len() as u32 + 1;
    let stamp = mix_pick_mark(zone, lane.net_kept_g, mark_idx);
    lane.pick_marks.push(stamp);
}

impl ZoneTracker {
    pub fn replay_settled(&mut self, picks: &[SettledPick]) {
        for row in picks {
            self.apply_one(row);
        }
    }

    fn apply_one(&mut self, row: &SettledPick) {
        if !self.lanes.contains_key(&row.zone) {
            self.order.push(row.zone.clone());
            self.lanes.insert(row.zone.clone(), Lane::default());
        }
        if row.voided {
            return;
        }
        let lane = self.lanes.get_mut(&row.zone).expect("lane");
        if row.refused_negative {
            record_refusal(lane);
            return;
        }
        if cap_exceeded(lane.net_kept_g, row.effective_net_g) {
            record_refusal(lane);
            return;
        }
        let mut grade = pick_grade(row.effective_net_g);
        if row.spoiled {
            grade = downgrade_grade(grade);
        }
        bump_grade(lane, grade);
        lane.net_kept_g += row.effective_net_g;
        lane.kept_rows += 1;
        if mark_cadence_hit(lane.kept_rows) {
            append_pick_mark(lane, &row.zone);
        }
    }

    pub fn zone_order(&self) -> Vec<String> {
        self.order.clone()
    }

    pub fn export_checkpoint(&self, zone: &str) -> Option<ZoneCheckpoint> {
        self.lanes.get(zone).map(|lane| ZoneCheckpoint {
            grade_prime: lane.grade_prime,
            grade_standard: lane.grade_standard,
            grade_cull: lane.grade_cull,
            net_kept_g: lane.net_kept_g,
            net_refused: lane.net_refused,
            pick_marks: lane.pick_marks.clone(),
            kept_rows: lane.kept_rows,
        })
    }

    pub fn import_checkpoint(&mut self, zone: &str, ckpt: ZoneCheckpoint) {
        if !self.lanes.contains_key(zone) {
            self.order.push(zone.to_string());
            self.lanes.insert(zone.to_string(), Lane::default());
        }
        if let Some(lane) = self.lanes.get_mut(zone) {
            lane.grade_prime = ckpt.grade_prime;
            lane.grade_standard = ckpt.grade_standard;
            lane.grade_cull = ckpt.grade_cull;
            lane.net_kept_g = ckpt.net_kept_g;
            lane.net_refused = ckpt.net_refused;
            lane.pick_marks = ckpt.pick_marks.clone();
            lane.kept_rows = ckpt.kept_rows;
        }
    }

    pub fn snapshot(&self) -> Vec<ZoneBalance> {
        self.order
            .iter()
            .map(|label| {
                let lane = &self.lanes[label];
                ZoneBalance {
                    zone: label.clone(),
                    grade_prime: lane.grade_prime,
                    grade_standard: lane.grade_standard,
                    grade_cull: lane.grade_cull,
                    net_kept_g: lane.net_kept_g,
                    net_refused: lane.net_refused,
                    pick_marks: lane.pick_marks.clone(),
                }
            })
            .collect()
    }
}
EOF

log "repair stamp payload and balance seal"
cat > /app/st/o4b/src/lib.rs <<'EOF'
use sha2::{Digest, Sha256};

fn stamp_body(zone: &str, kept: u64, mark_idx: u32) -> String {
    format!("{}|{}|{}", zone, kept, mark_idx)
}

pub fn mix_pick_mark(zone: &str, kept: u64, mark_idx: u32) -> String {
    let payload = stamp_body(zone, kept, mark_idx);
    let digest = Sha256::digest(payload.as_bytes());
    hex::encode(digest)
}

pub fn seal_balance(
    parts: &[String],
    tare_lineage: &str,
    supersede_lineage: &str,
    spoilage_lineage: &str,
) -> String {
    let marks_part = parts.join(";");
    let mut payload = marks_part;
    if !tare_lineage.is_empty() {
        payload = if payload.is_empty() {
            tare_lineage.to_string()
        } else {
            format!("{};{}", payload, tare_lineage)
        };
    }
    if !supersede_lineage.is_empty() {
        payload = if payload.is_empty() {
            supersede_lineage.to_string()
        } else {
            format!("{};{}", payload, supersede_lineage)
        };
    }
    if !spoilage_lineage.is_empty() {
        payload = if payload.is_empty() {
            spoilage_lineage.to_string()
        } else {
            format!("{};{}", payload, spoilage_lineage)
        };
    }
    let digest = Sha256::digest(payload.as_bytes());
    hex::encode(digest)
}

mod hex {
    pub fn encode(bytes: impl AsRef<[u8]>) -> String {
        bytes
            .as_ref()
            .iter()
            .map(|b| format!("{:02x}", b))
            .collect()
    }
}
EOF

log "repair spoilage generation ordering"
sed -i 's/row.generation.to_string() > prev.generation.to_string()/row.generation > prev.generation/' /app/st/o7x/src/lib.rs

log "repair supersede and spoilage lineage stamping"
python3 - <<'PY'
from pathlib import Path

path = Path("/app/st/o7x/src/lib.rs")
text = path.read_text()
old_sup = """pub fn supersede_lineage(
    supersedes: &[SupersedeLine],
    winners: &HashMap<String, SupersedeWinner>,
) -> String {
    let mut parts = Vec::new();
    for sup in supersedes {
        let Some(winner) = winners.get(&sup.target_pick_id) else {
            continue;
        };
        if winner.generation != sup.generation {
            continue;
        }
        let value = if winner.action == "void" {
            "VOID".to_string()
        } else {
            winner.gross_g.to_string()
        };
        parts.push(format!(
            "{}|{}|{}|{}",
            sup.target_pick_id, sup.generation, sup.action, value
        ));
    }
    parts.join(";")
}"""
new_sup = """fn supersede_row_matches(sup: &SupersedeLine, winner: &SupersedeWinner) -> bool {
    sup.generation == winner.generation
        && sup.action == winner.action
        && (winner.action != "replace" || sup.gross_g == winner.gross_g)
}

pub fn supersede_lineage(
    supersedes: &[SupersedeLine],
    winners: &HashMap<String, SupersedeWinner>,
) -> String {
    let mut parts = Vec::new();
    let mut emitted = std::collections::HashSet::new();
    for sup in supersedes {
        if emitted.contains(&sup.target_pick_id) {
            continue;
        }
        let Some(winner) = winners.get(&sup.target_pick_id) else {
            continue;
        };
        if !supersede_row_matches(sup, winner) {
            continue;
        }
        emitted.insert(sup.target_pick_id.clone());
        let value = if winner.action == "void" {
            "VOID".to_string()
        } else {
            winner.gross_g.to_string()
        };
        parts.push(format!(
            "{}|{}|{}|{}",
            sup.target_pick_id, sup.generation, sup.action, value
        ));
    }
    parts.join(";")
}"""
old_spoil = """pub fn spoilage_lineage(
    spoilages: &[SpoilageLine],
    winners: &HashMap<String, SpoilageWinner>,
) -> String {
    let mut parts = Vec::new();
    for row in spoilages {
        let Some(winner) = winners.get(&row.target_pick_id) else {
            continue;
        };
        if winner.generation != row.generation {
            continue;
        }
        parts.push(format!("{}|{}", row.target_pick_id, row.generation));
    }
    parts.join(";")
}"""
new_spoil = """pub fn spoilage_lineage(
    spoilages: &[SpoilageLine],
    winners: &HashMap<String, SpoilageWinner>,
) -> String {
    let mut parts = Vec::new();
    let mut emitted = std::collections::HashSet::new();
    for row in spoilages {
        if emitted.contains(&row.target_pick_id) {
            continue;
        }
        let Some(winner) = winners.get(&row.target_pick_id) else {
            continue;
        };
        if winner.generation != row.generation {
            continue;
        }
        emitted.insert(row.target_pick_id.clone());
        parts.push(format!("{}|{}", row.target_pick_id, row.generation));
    }
    parts.join(";")
}"""
if old_sup not in text:
    raise SystemExit("supersede_lineage block not found")
if old_spoil not in text:
    raise SystemExit("spoilage_lineage block not found")
text = text.replace(old_sup, new_sup).replace(old_spoil, new_spoil)
path.write_text(text)
PY

log "repair balance report checkpoint_used"
python3 - <<'PY'
from pathlib import Path

path = Path("/app/hv/o0m/src/lib.rs")
text = path.read_text()
old = """pub struct BalanceReport {
    pub zones: Vec<ZoneBalance>,
    pub balance_stamp: String,
}"""
new = """pub struct BalanceReport {
    pub zones: Vec<ZoneBalance>,
    pub balance_stamp: String,
    pub checkpoint_used: bool,
}"""
if old not in text:
    raise SystemExit("BalanceReport block not found")
path.write_text(text.replace(old, new))
PY

log "repair checkpoint validation"
python3 - <<'PY'
from pathlib import Path

path = Path("/app/hv/o0m/src/lib.rs")
text = path.read_text()
zone_needle = """#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ZoneCheckpoint {"""
zone_replacement = """#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct ZoneCheckpoint {"""
replay_needle = """#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReplayCheckpoint {"""
replay_replacement = """#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReplayCheckpoint {"""
if zone_needle not in text:
    raise SystemExit("ZoneCheckpoint derive block not found")
if replay_needle not in text:
    raise SystemExit("ReplayCheckpoint derive block not found")
text = text.replace(zone_needle, zone_replacement, 1)
text = text.replace(replay_needle, replay_replacement, 1)
path.write_text(text)
PY

cat > /app/st/o8w/src/lib.rs <<'EOF'
use std::collections::{HashMap, HashSet};
use std::fs;
use std::io::Read;
use std::path::Path;

use o0m::{
    ReplayCheckpoint, SCHEMA_GENERATION, SpoilageWinner, SupersedeWinner, ZoneCheckpoint,
    CAP_NET_G, PICK_MARK_CADENCE,
};

use sha2::Digest;

pub fn input_identity(path: &Path) -> Result<String, String> {
    let mut file = fs::File::open(path).map_err(|e| e.to_string())?;
    let mut buf = Vec::new();
    file.read_to_end(&mut buf).map_err(|e| e.to_string())?;
    let digest = sha2::Sha256::digest(&buf);
    Ok(hex::encode(digest))
}

fn winners_match<T: PartialEq + Clone>(
    current: &HashMap<String, T>,
    stored: &HashMap<String, T>,
) -> bool {
    current == stored
}

fn hex_digest_valid(value: &str) -> bool {
    value.len() == 64
        && value
            .chars()
            .all(|c| c.is_ascii_hexdigit() && !c.is_ascii_uppercase())
}

fn mark_valid(mark: &str) -> bool {
    hex_digest_valid(mark)
}

fn kept_rows_consistent(state: &ZoneCheckpoint) -> bool {
    let accepted = state.grade_prime + state.grade_standard + state.grade_cull;
    state.kept_rows == accepted
        && state.pick_marks.len() as u32 == state.kept_rows / PICK_MARK_CADENCE
}

fn zone_state_valid(state: &ZoneCheckpoint) -> bool {
    state.net_kept_g <= CAP_NET_G
        && state.pick_marks.iter().all(|mark| mark_valid(mark))
        && kept_rows_consistent(state)
}

pub fn zone_states_accept(ckpt: &ReplayCheckpoint) -> bool {
    let expected: HashSet<&str> = ckpt.zone_order.iter().map(|s| s.as_str()).collect();
    if expected.is_empty() || ckpt.zone_states.len() != expected.len() {
        return false;
    }
    for zone in &ckpt.zone_order {
        let Some(state) = ckpt.zone_states.get(zone) else {
            return false;
        };
        if !zone_state_valid(state) {
            return false;
        }
    }
    ckpt.zone_states
        .keys()
        .all(|key| expected.contains(key.as_str()))
}

pub fn zone_states_match_cold(
    ckpt: &ReplayCheckpoint,
    cold: &HashMap<String, ZoneCheckpoint>,
) -> bool {
    if !zone_states_accept(ckpt) {
        return false;
    }
    for zone in &ckpt.zone_order {
        let Some(stored) = ckpt.zone_states.get(zone) else {
            return false;
        };
        let Some(expected) = cold.get(zone) else {
            return false;
        };
        if stored != expected {
            return false;
        }
    }
    true
}

fn seal_balance(
    parts: &[String],
    tare_lineage: &str,
    supersede_lineage: &str,
    spoilage_lineage: &str,
) -> String {
    let marks_part = parts.join(";");
    let mut payload = marks_part;
    if !tare_lineage.is_empty() {
        payload = if payload.is_empty() {
            tare_lineage.to_string()
        } else {
            format!("{};{}", payload, tare_lineage)
        };
    }
    if !supersede_lineage.is_empty() {
        payload = if payload.is_empty() {
            supersede_lineage.to_string()
        } else {
            format!("{};{}", payload, supersede_lineage)
        };
    }
    if !spoilage_lineage.is_empty() {
        payload = if payload.is_empty() {
            spoilage_lineage.to_string()
        } else {
            format!("{};{}", payload, spoilage_lineage)
        };
    }
    let digest = sha2::Sha256::digest(payload.as_bytes());
    hex::encode(digest)
}

pub fn wal_identity_accept(
    ckpt: &ReplayCheckpoint,
    identity: &str,
    tare_lineage: &str,
    supersede_winners: &HashMap<String, SupersedeWinner>,
    spoilage_winners: &HashMap<String, SpoilageWinner>,
    last_event_position: u64,
    expected_stamp_seed: &str,
    cold_zone_states: &HashMap<String, ZoneCheckpoint>,
    zone_order: &[String],
) -> bool {
    ckpt.schema_generation == SCHEMA_GENERATION
        && !ckpt.zone_order.is_empty()
        && ckpt.zone_order == zone_order
        && hex_digest_valid(&ckpt.input_identity)
        && ckpt.input_identity == identity
        && ckpt.tare_lineage == tare_lineage
        && winners_match(supersede_winners, &ckpt.supersede_winners)
        && winners_match(spoilage_winners, &ckpt.spoilage_winners)
        && ckpt.last_event_position == last_event_position
        && hex_digest_valid(&ckpt.previous_stamp_seed)
        && ckpt.previous_stamp_seed == expected_stamp_seed
        && zone_states_match_cold(ckpt, cold_zone_states)
}

fn hydrated_stamp_matches(
    ckpt: &ReplayCheckpoint,
    tare_lineage: &str,
    supersede_lineage: &str,
    spoilage_lineage: &str,
) -> bool {
    let marks: Vec<String> = ckpt
        .zone_order
        .iter()
        .flat_map(|zone| {
            ckpt.zone_states
                .get(zone)
                .map(|state| state.pick_marks.clone())
                .unwrap_or_default()
        })
        .collect();
    seal_balance(
        &marks,
        tare_lineage,
        supersede_lineage,
        spoilage_lineage,
    ) == ckpt.previous_stamp_seed
}

pub fn continuation_accept(
    ckpt: &ReplayCheckpoint,
    identity: &str,
    tare_lineage: &str,
    supersede_winners: &HashMap<String, SupersedeWinner>,
    spoilage_winners: &HashMap<String, SpoilageWinner>,
    suffix_last_pos: u64,
    supersede_lineage: &str,
    spoilage_lineage: &str,
    zone_order: &[String],
) -> bool {
    ckpt.schema_generation == SCHEMA_GENERATION
        && !ckpt.zone_order.is_empty()
        && ckpt.zone_order == zone_order
        && hex_digest_valid(&ckpt.input_identity)
        && ckpt.input_identity == identity
        && ckpt.tare_lineage == tare_lineage
        && winners_match(supersede_winners, &ckpt.supersede_winners)
        && winners_match(spoilage_winners, &ckpt.spoilage_winners)
        && ckpt.last_event_position > suffix_last_pos
        && hex_digest_valid(&ckpt.previous_stamp_seed)
        && zone_states_accept(ckpt)
        && hydrated_stamp_matches(ckpt, tare_lineage, supersede_lineage, spoilage_lineage)
}

pub fn load_checkpoint(path: &Path) -> Result<ReplayCheckpoint, String> {
    let body = fs::read_to_string(path).map_err(|e| e.to_string())?;
    serde_json::from_str(&body).map_err(|e| e.to_string())
}

pub fn write_checkpoint(path: &Path, ckpt: &ReplayCheckpoint) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let body = serde_json::to_string_pretty(ckpt).map_err(|e| e.to_string())?;
    fs::write(path, body + "\n").map_err(|e| e.to_string())
}

mod hex {
    pub fn encode(bytes: impl AsRef<[u8]>) -> String {
        bytes
            .as_ref()
            .iter()
            .map(|b| format!("{:02x}", b))
            .collect()
    }
}
EOF

log "repair checkpoint resume binding"
python3 - <<'PY'
from pathlib import Path

path = Path("/app/fx/o9b/src/main.rs")
text = path.read_text()
old = """    let order = zone_order_from_picks(&feed);

    let mut tracker = ZoneTracker::default();
    let mut resumed = false;
    if let Some(ckpt_path) = checkpoint_in {
        if let Ok(ckpt) = load_checkpoint(&ckpt_path) {
            if wal_identity_accept(
                &ckpt,
                &identity,
                &tare_lineage,
                &supersede_winners,
                &spoilage_winners,
            ) {
                for zone in &ckpt.zone_order {
                    if let Some(state) = ckpt.zone_states.get(zone) {
                        tracker.import_checkpoint(zone, state.clone());
                    }
                }
                resumed = true;
            }
        }
    }
    if !resumed {
        tracker.replay_settled(&settled);
    }"""
new = """    let order = zone_order_from_picks(&feed);
    let last_pos = feed.events.last().map(|e| e.position).unwrap_or(0);

    let mut cold_tracker = ZoneTracker::default();
    cold_tracker.replay_settled(&settled);
    let cold_zones = layout_zones(cold_tracker.snapshot());
    let mut cold_zone_states = HashMap::new();
    for zone in &order {
        if let Some(state) = cold_tracker.export_checkpoint(zone) {
            cold_zone_states.insert(zone.clone(), state);
        }
    }
    let cold_marks: Vec<String> = cold_zones
        .iter()
        .flat_map(|z| z.pick_marks.clone())
        .collect();
    let expected_stamp = seal_balance(
        &cold_marks,
        &tare_lineage,
        &supersede_lin,
        &spoilage_lin,
    );

    let mut tracker = ZoneTracker::default();
    let mut resumed = false;
    let mut continuation = false;
    if let Some(ckpt_path) = checkpoint_in {
        if let Ok(ckpt) = load_checkpoint(&ckpt_path) {
            if wal_identity_accept(
                &ckpt,
                &identity,
                &tare_lineage,
                &supersede_winners,
                &spoilage_winners,
                last_pos,
                &expected_stamp,
                &cold_zone_states,
                &order,
            ) {
                for zone in &ckpt.zone_order {
                    if let Some(state) = ckpt.zone_states.get(zone) {
                        tracker.import_checkpoint(zone, state.clone());
                    }
                }
                let hydrated_zones = layout_zones(tracker.snapshot());
                let hydrated_marks: Vec<String> = hydrated_zones
                    .iter()
                    .flat_map(|z| z.pick_marks.clone())
                    .collect();
                let hydrated_stamp = seal_balance(
                    &hydrated_marks,
                    &tare_lineage,
                    &supersede_lin,
                    &spoilage_lin,
                );
                let hydrated_zone_states: HashMap<String, _> = order
                    .iter()
                    .filter_map(|zone| {
                        tracker
                            .export_checkpoint(zone)
                            .map(|state| (zone.clone(), state))
                    })
                    .collect();
                if hydrated_zones == cold_zones
                    && hydrated_stamp == expected_stamp
                    && hydrated_zone_states == cold_zone_states
                {
                    resumed = true;
                } else {
                    tracker = ZoneTracker::default();
                }
            } else if continuation_accept(
                &ckpt,
                &identity,
                &tare_lineage,
                &supersede_winners,
                &spoilage_winners,
                last_pos,
                &supersede_lin,
                &spoilage_lin,
                &order,
            ) {
                for zone in &ckpt.zone_order {
                    if let Some(state) = ckpt.zone_states.get(zone) {
                        tracker.import_checkpoint(zone, state.clone());
                    }
                }
                resumed = true;
                continuation = true;
            }
        }
    }
    if continuation {
        tracker.replay_settled(&settled);
    } else if !resumed {
        tracker.replay_settled(&settled);
    }"""
if old not in text:
    raise SystemExit("checkpoint resume block not found in pick-balance driver")
path.write_text(text.replace(old, new))
PY

log "repair checkpoint_used report field"
python3 - <<'PY'
from pathlib import Path

path = Path("/app/fx/o9b/src/main.rs")
text = path.read_text()
old_import = "use o8w::{input_identity, load_checkpoint, wal_identity_accept, write_checkpoint};"
new_import = "use o8w::{continuation_accept, input_identity, load_checkpoint, wal_identity_accept, write_checkpoint};"
if old_import not in text:
    raise SystemExit("o8w import block not found")
text = text.replace(old_import, new_import, 1)
old = """    let report = BalanceReport {
        zones,
        balance_stamp: seal_balance(
            &stamp_parts,
            &tare_lineage,
            &supersede_lin,
            &spoilage_lin,
        ),
    };"""
new = """    let report = BalanceReport {
        zones,
        balance_stamp: seal_balance(
            &stamp_parts,
            &tare_lineage,
            &supersede_lin,
            &spoilage_lin,
        ),
        checkpoint_used: resumed,
    };"""
if old not in text:
    raise SystemExit("BalanceReport construction block not found")
path.write_text(text.replace(old, new))
PY

log "repair emit ordering"
sed -i 's/rows.sort_by(|a, b| a.zone.cmp(&b.zone));/let _ = rows;/' /app/fx/o5r/src/lib.rs
sed -i '/rows.dedup_by(|a, b| a.zone == b.zone);/d' /app/fx/o5r/src/lib.rs

log "rebuild release driver"
make -C /app APP_ROOT=/app all

log "regenerate balance report"
mkdir -p /app/output
/app/bin/pick-balance --input /app/data/feed.jsonl --out /app/output/pick_report.json

log "done"

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

fn cap_exceeded(kept: u64, _incoming: u64) -> bool {
    kept >= CAP_NET_G
}

fn mark_cadence_hit(kept_rows: u32) -> bool {
    let cadence = PICK_MARK_CADENCE - 1;
    kept_rows % cadence == 0
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
        let lane = self.lanes.get_mut(&row.zone).expect("lane");
        lane.kept_rows += 1;
        if row.voided {
            if mark_cadence_hit(lane.kept_rows) {
                append_pick_mark(lane, &row.zone);
            }
            return;
        }
        if row.refused_negative {
            record_refusal(lane);
            return;
        }
        if cap_exceeded(lane.net_kept_g, row.effective_net_g) {
            record_refusal(lane);
            return;
        }
        let mut grade = pick_grade(row.gross_g);
        if row.spoiled {
            grade = downgrade_grade(grade);
        }
        bump_grade(lane, grade);
        lane.net_kept_g += row.effective_net_g;
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

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

pub const OUT_DIR: &str = "/app/output";
pub const MAX_U64: u64 = 9_223_372_036_854_775_807;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct BufferIn {
    pub buffer_id: String,
    pub capacity: u64,
    pub status: String,
}

#[derive(Debug, Deserialize, Clone)]
#[serde(deny_unknown_fields)]
pub struct EventIn {
    pub event_id: String,
    pub timestamp: i64,
    pub op: String,
    pub buffer_id: String,
    pub lane_id: String,
    pub qty: String,
    #[serde(default)]
    pub peer_buffer_id: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct BufferOut {
    pub available: u64,
    pub buffer_id: String,
    pub capacity: u64,
    pub dispatched: u64,
    pub filled: u64,
    pub holdback: u64,
    pub status: String,
}

#[derive(Debug, Serialize)]
pub struct SummaryOut {
    pub applied_events: u64,
    pub buffers_total: u64,
    pub duplicate_events: u64,
    pub rejected_events: u64,
    pub total_dispatched: u64,
    pub total_filled: u64,
    pub total_holdback: u64,
}

#[derive(Debug, Serialize)]
pub struct ResultOut {
    pub buffers: Vec<BufferOut>,
    pub summary: SummaryOut,
}

#[derive(Debug)]
pub struct BufferState {
    pub capacity: u64,
    pub status: String,
    pub filled: u64,
    pub holdback: u64,
    pub dispatched: u64,
    pub lane_filled: BTreeMap<String, u64>,
    pub lane_holdback: BTreeMap<String, u64>,
}

impl BufferState {
    pub fn available(&self) -> u64 {
        self.capacity
            .saturating_sub(self.filled)
            .saturating_sub(self.holdback)
    }

    pub fn lane_filled(&self, lane: &str) -> u64 {
        self.lane_filled.get(lane).copied().unwrap_or(0)
    }

    pub fn lane_holdback(&self, lane: &str) -> u64 {
        self.lane_holdback.get(lane).copied().unwrap_or(0)
    }

    pub fn add_lane_filled(&mut self, lane: &str, qty: u64) {
        *self.lane_filled.entry(lane.to_string()).or_insert(0) += qty;
        self.filled += qty;
    }

    pub fn add_lane_holdback(&mut self, lane: &str, qty: u64) {
        *self.lane_holdback.entry(lane.to_string()).or_insert(0) += qty;
        self.holdback += qty;
    }

    pub fn take_lane_filled(&mut self, lane: &str, qty: u64) -> u64 {
        let have = self.lane_filled(lane);
        let take = qty.min(have);
        if take == 0 {
            return 0;
        }
        let entry = self.lane_filled.get_mut(lane).unwrap();
        *entry -= take;
        if *entry == 0 {
            self.lane_filled.remove(lane);
        }
        self.filled -= take;
        take
    }

    pub fn take_lane_holdback(&mut self, lane: &str, qty: u64) -> u64 {
        let have = self.lane_holdback(lane);
        let take = qty.min(have);
        if take == 0 {
            return 0;
        }
        let entry = self.lane_holdback.get_mut(lane).unwrap();
        *entry -= take;
        if *entry == 0 {
            self.lane_holdback.remove(lane);
        }
        self.holdback -= take;
        take
    }

    pub fn take_holdback_lex(&mut self, qty: u64) -> u64 {
        let mut remain = qty;
        let mut lanes: Vec<String> = self.lane_holdback.keys().cloned().collect();
        lanes.sort_by(|a, b| b.cmp(a));
        let mut taken = 0u64;
        for lane in lanes {
            if remain == 0 {
                break;
            }
            let take = remain.min(self.lane_holdback(&lane));
            if take > 0 {
                taken += self.take_lane_holdback(&lane, take);
                remain -= take;
            }
        }
        taken
    }

    pub fn take_filled_lex(&mut self, qty: u64) -> u64 {
        let mut remain = qty;
        let mut lanes: Vec<String> = self.lane_filled.keys().cloned().collect();
        lanes.sort_by(|a, b| b.cmp(a));
        let mut taken = 0u64;
        for lane in lanes {
            if remain == 0 {
                break;
            }
            let take = remain.min(self.lane_filled(&lane));
            if take > 0 {
                taken += self.take_lane_filled(&lane, take);
                remain -= take;
            }
        }
        taken
    }
}

#[derive(Debug)]
pub struct EventRec {
    pub rel: String,
    pub line: u64,
    pub event: EventIn,
}

#[derive(Debug)]
pub struct AuditRow {
    pub event_id: String,
    pub timestamp: i64,
    pub buffer_id: String,
    pub lane_id: String,
    pub applied_qty: u64,
}

#[derive(Debug)]
pub struct RejectRow {
    pub event_id: String,
    pub timestamp: i64,
    pub buffer_id: String,
    pub reason: &'static str,
}

pub fn read_utf8(path: &Path) -> Result<String, ()> {
    String::from_utf8(fs::read(path).map_err(|_| ())?).map_err(|_| ())
}

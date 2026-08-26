use std::fs;
use std::path::Path;

use crate::types::{JournalHeader, Manifest};

#[derive(Debug, Clone)]
pub struct ParsedRecord {
    pub scope_id: u32,
    pub action_mask: u32,
    pub size_delta: i32,
    pub seq_num: u32,
    pub ts_ms: u64,
    pub rel_path: String,
    pub payload: Vec<u8>,
}

#[derive(Debug, Clone)]
pub struct ParsedJournal {
    pub header: JournalHeader,
    pub records: Vec<ParsedRecord>,
}

pub fn load_manifest(path: &Path) -> Manifest {
    let raw = fs::read_to_string(path).expect("manifest");
    let v: serde_json::Value = serde_json::from_str(&raw).expect("manifest json");
    Manifest {
        bound_rotate: v["bound_rotate"].as_u64().unwrap() as u32,
        slack: v["slack"].as_u64().unwrap() as u32,
        sweep_mask: v["sweep_mask"].as_u64().unwrap() as u32,
        window_width_ms: v["window_width_ms"].as_u64().unwrap(),
        manifest_gen: v["manifest_gen"].as_u64().unwrap() as u32,
    }
}

pub fn read_journal(path: &Path) -> ParsedJournal {
    let data = fs::read(path).expect("journal");
    let header = parse_header(&data);
    let record_count = u32::from_le_bytes(data[16..20].try_into().unwrap()) as usize;
    let mut off = 32usize;
    let mut records = Vec::new();
    for _ in 0..record_count {
        if off >= data.len() {
            break;
        }
        let (rec, consumed) = parse_record(&data[off..]);
        records.push(rec);
        off += consumed;
    }
    ParsedJournal { header, records }
}

fn parse_header(data: &[u8]) -> JournalHeader {
    let rotate_gen = u32::from_be_bytes(data[4..8].try_into().unwrap());
    let bound_rotate = u32::from_le_bytes(data[8..12].try_into().unwrap());
    let slack = u32::from_le_bytes(data[12..16].try_into().unwrap());
    JournalHeader {
        rotate_gen,
        bound_rotate,
        slack,
    }
}

fn parse_record(data: &[u8]) -> (ParsedRecord, usize) {
    let scope_id = u32::from_le_bytes(data[0..4].try_into().unwrap());
    let action_mask = u32::from_le_bytes(data[4..8].try_into().unwrap());
    let size_delta = i32::from_le_bytes(data[8..12].try_into().unwrap());
    let seq_num = u32::from_le_bytes(data[12..16].try_into().unwrap());
    let ts_ms = u64::from_le_bytes(data[16..24].try_into().unwrap());
    let path_len = u16::from_le_bytes(data[24..26].try_into().unwrap()) as usize;
    let mut off = 26usize;
    let rel_path = String::from_utf8_lossy(&data[off..off + path_len]).into_owned();
    off += path_len;
    let payload_len = u32::from_le_bytes(data[off..off + 4].try_into().unwrap()) as usize;
    off += 4;
    let payload = data[off..off + payload_len].to_vec();
    off += payload_len;
    (
        ParsedRecord {
            scope_id,
            action_mask,
            size_delta,
            seq_num,
            ts_ms,
            rel_path,
            payload,
        },
        off,
    )
}

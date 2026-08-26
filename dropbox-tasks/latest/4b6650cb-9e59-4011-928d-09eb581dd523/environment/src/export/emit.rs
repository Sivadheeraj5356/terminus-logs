use std::fs;
use std::path::Path;

use crate::types::{ProbeSnapshot, SweepLedger};

const BASIS: u64 = 0xB001_7000_CAFEBABE;
const MULT: u64 = 137;

pub fn roll_buffer(buf: &[u8]) -> u64 {
    let mut h = BASIS;
    for &b in buf {
        h = h.wrapping_mul(MULT).wrapping_add(b as u64);
    }
    h ^ buf.len() as u64
}

pub fn records_digest(payloads: &[Vec<u8>]) -> u64 {
    let mut buf = Vec::new();
    for p in payloads {
        buf.extend_from_slice(p);
    }
    roll_buffer(&buf)
}

pub fn write_ledger(reg: &SweepLedger) {
    let out_dir = Path::new("/app/output");
    fs::create_dir_all(out_dir).ok();
    let json = serde_json::to_string_pretty(reg).expect("ledger json");
    fs::write(out_dir.join("sweep_ledger.json"), json).expect("write ledger");
}

pub fn write_probe(snap: &ProbeSnapshot) {
    let out_dir = Path::new("/app/output");
    fs::create_dir_all(out_dir).ok();
    let json = serde_json::to_string_pretty(snap).expect("probe json");
    fs::write(out_dir.join("probe_snapshot.json"), json).expect("write probe");
}

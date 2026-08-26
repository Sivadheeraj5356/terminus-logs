use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

use crate::shared::tls_codec::{observation_digest, sha256_hex};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct LaneStamp {
    pub host_id: String,
    pub lane_id: String,
    pub cohort_label: String,
    pub stamp_hex: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RunWal {
    pub generation: u32,
    pub prior_digest: String,
    pub last_digest: String,
    pub plan_hash: String,
    pub lane_stamps: Vec<LaneStamp>,
    pub recovered: bool,
}

impl Default for RunWal {
    fn default() -> Self {
        Self {
            generation: 0,
            prior_digest: String::new(),
            last_digest: String::new(),
            plan_hash: String::new(),
            lane_stamps: Vec::new(),
            recovered: false,
        }
    }
}

pub fn digest_valid(d: &str) -> bool {
    d.len() == 64 && d.chars().all(|c| c.is_ascii_hexdigit())
}

pub fn wal_path() -> PathBuf {
    Path::new("/app/var/run_journal.json").to_path_buf()
}

pub fn route_plan_path() -> PathBuf {
    Path::new("/app/var/route_plan.json").to_path_buf()
}

pub fn ensure_var_dir() {
    let _ = std::fs::create_dir_all("/app/var");
}

pub fn load_wal(path: &Path) -> RunWal {
    let raw = match std::fs::read_to_string(path) {
        Ok(s) => s,
        Err(_) => return RunWal::default(),
    };
    match serde_json::from_str::<RunWal>(&raw) {
        Ok(j) => j,
        Err(_) => {
            let mut wal = RunWal {
                recovered: true,
                ..RunWal::default()
            };
            if let Some(generation) = scrape_json_u32(&raw, "generation") {
                wal.generation = generation;
            }
            if let Some(prior_digest) = scrape_json_string(&raw, "prior_digest") {
                wal.prior_digest = prior_digest;
            }
            if let Some(last_digest) = scrape_json_string(&raw, "last_digest") {
                wal.last_digest = last_digest;
            }
            if let Some(plan_hash) = scrape_json_string(&raw, "plan_hash") {
                wal.plan_hash = plan_hash;
            }
            wal
        }
    }
}

fn scrape_json_u32(raw: &str, key: &str) -> Option<u32> {
    let needle = format!("\"{key}\":");
    let start = raw.find(&needle)? + needle.len();
    let rest = raw[start..].trim_start();
    let end = rest
        .find(|c: char| !c.is_ascii_digit())
        .unwrap_or(rest.len());
    rest[..end].parse().ok()
}

fn scrape_json_string(raw: &str, key: &str) -> Option<String> {
    let needle = format!("\"{key}\":\"");
    let start = raw.find(&needle)? + needle.len();
    let rest = &raw[start..];
    if let Some(end) = rest.find('"') {
        Some(rest[..end].to_string())
    } else {
        Some(rest.to_string())
    }
}

pub fn lane_stamp_hex(
    host_id: &str,
    lane_id: &str,
    cohort_label: &str,
    rewrite_count: u32,
    fingerprint: &str,
) -> String {
    let body = format!(
        "{host_id}|{lane_id}|{cohort_label}|{rewrite_count}|{fingerprint}"
    );
    sha256_hex(body.as_bytes())
}

pub fn commit_wal(
    path: &Path,
    prev: &RunWal,
    lane_stamps: &[LaneStamp],
    observation_digest: &str,
    plan_hash: &str,
) -> RunWal {
    let next = RunWal {
        generation: prev.generation.saturating_add(1),
        prior_digest: prev.last_digest.clone(),
        last_digest: observation_digest.to_string(),
        plan_hash: plan_hash.to_string(),
        lane_stamps: lane_stamps.to_vec(),
        recovered: false,
    };
    let body = serde_json::to_string_pretty(&next).unwrap_or_else(|_| "{}".into());
    let _ = std::fs::write(path, format!("{body}\n"));
    next
}

pub fn wal_chain_digest(wal: &RunWal, observation_digest: &str) -> String {
    let stamp_body = serde_json::to_string(&wal.lane_stamps).unwrap_or_else(|_| "[]".into());
    let body = format!(
        "{}|{}|{}|{}|{}",
        wal.generation,
        wal.prior_digest,
        observation_digest,
        wal.plan_hash,
        stamp_body
    );
    sha256_hex(body.as_bytes())
}

pub fn reconcile_truncated(
    wal: &mut RunWal,
    rows: &[serde_json::Value],
    plan_hash: &str,
) {
    if !wal.recovered {
        return;
    }
    wal.plan_hash = plan_hash.to_string();
    wal.lane_stamps = rows
        .iter()
        .map(|row| LaneStamp {
            host_id: row["host_id"].as_str().unwrap_or("").to_string(),
            lane_id: row["lane_id"].as_str().unwrap_or("").to_string(),
            cohort_label: row["cohort_label"].as_str().unwrap_or("").to_string(),
            stamp_hex: lane_stamp_hex(
                row["host_id"].as_str().unwrap_or(""),
                row["lane_id"].as_str().unwrap_or(""),
                row["cohort_label"].as_str().unwrap_or(""),
                row["rewrite_count"].as_u64().unwrap_or(0) as u32,
                row["material_fingerprint"].as_str().unwrap_or(""),
            ),
        })
        .collect();
    wal.recovered = false;
}

pub fn digest_rows(rows: &[serde_json::Value]) -> String {
    observation_digest(rows)
}

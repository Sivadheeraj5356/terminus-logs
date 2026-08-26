use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ModeSpec {
    pub mode: String,
    pub resident_cap: u64,
    pub decay_modulus: u64,
    pub decay_phase: u64,
    pub tick_scale: u64,
    pub cell_bytes: u64,
    pub fade_start: u32,
    pub group_header_bytes: u64,
    pub observer_metadata_bytes: u64,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ObserverSpec {
    pub oid: u16,
    pub cx: u32,
    pub cy: u32,
    pub reach: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ObserverPhase {
    pub until_tick: u64,
    pub observers: Vec<ObserverSpec>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ScenarioSpec {
    pub id: String,
    pub mode: String,
    pub observers: Vec<ObserverSpec>,
    #[serde(default)]
    pub observer_phases: Vec<ObserverPhase>,
    pub ally_groups: Vec<Vec<u16>>,
    pub slots: usize,
    #[serde(default)]
    pub grid_width: usize,
    #[serde(default)]
    pub grid_height: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MergeRow {
    pub group: Vec<u16>,
    pub handle: u16,
    pub copies: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct RunRow {
    pub scenario_id: String,
    pub footprint_band: String,
    pub peak_bytes: u64,
    pub bitplane_digests: HashMap<String, String>,
    pub merge_lineage: Vec<MergeRow>,
    pub decay_trace: Vec<u32>,
    pub explored_count: u32,
    pub sensor_count: u32,
    pub stale_count: u32,
    pub fade_checksum: String,
    pub observer_pool_digest: String,
    pub plane_delta_digest: String,
    pub cadence_trace: Vec<String>,
    pub resident_trace: Vec<String>,
    pub recovery_epoch: u32,
    pub run_digest: String,
    pub plane_trace: Vec<String>,
    pub cadence_trace_v3: Vec<String>,
    pub pool_trace: Vec<String>,
    pub source_refs: Vec<String>,
    pub run_v3_digest: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct LedgerDoc {
    pub schema_version: u32,
    pub suite: String,
    pub ticks: u64,
    pub peak_resident_bytes: u64,
    pub resident_cap_bytes: u64,
    pub footprint_band: String,
    pub runs: Vec<RunRow>,
    pub orchestrator_phases: Vec<String>,
    pub worker_phases: Vec<String>,
    pub source_digest: String,
    pub phase_digest: String,
    pub ledger_digest: String,
    pub plane_trace_digest: String,
    pub cadence_digest: String,
    pub pool_trace_digest: String,
    pub scenario_digest: String,
}

pub fn load_mode(env: &Path, mode: &str) -> ModeSpec {
    let raw = fs::read_to_string(env.join("specs_r").join(format!("{mode}.toml"))).unwrap_or_default();
    let mut spec = ModeSpec {
        mode: mode.to_string(),
        resident_cap: 8192,
        decay_modulus: 4,
        decay_phase: 0,
        tick_scale: 10,
        cell_bytes: 64,
        fade_start: 6,
        group_header_bytes: 32,
        observer_metadata_bytes: 16,
    };
    for line in raw.lines() {
        let Some((k, v)) = line.split_once('=') else { continue };
        let k = k.trim();
        let v = v.trim();
        match k {
            "resident_cap" => spec.resident_cap = v.parse().unwrap_or(spec.resident_cap),
            "decay_modulus" => spec.decay_modulus = v.parse().unwrap_or(spec.decay_modulus),
            "decay_phase" => spec.decay_phase = v.parse().unwrap_or(spec.decay_phase),
            "tick_scale" => spec.tick_scale = v.parse().unwrap_or(spec.tick_scale),
            "cell_bytes" => spec.cell_bytes = v.parse().unwrap_or(spec.cell_bytes),
            "fade_start" => spec.fade_start = v.parse().unwrap_or(spec.fade_start),
            "group_header_bytes" => {
                spec.group_header_bytes = v.parse().unwrap_or(spec.group_header_bytes)
            }
            "observer_metadata_bytes" => {
                spec.observer_metadata_bytes = v.parse().unwrap_or(spec.observer_metadata_bytes)
            }
            _ => {}
        }
    }
    spec
}

pub fn load_scenario(env: &Path, case_id: &str) -> ScenarioSpec {
    let p = env.join("cases/g2").join(format!("{case_id}.json"));
    let raw = fs::read_to_string(p).unwrap_or_default();
    let mut spec: ScenarioSpec = serde_json::from_str(&raw).unwrap_or(ScenarioSpec {
        id: case_id.to_string(),
        mode: "r0".to_string(),
        observers: vec![],
        observer_phases: vec![],
        ally_groups: vec![],
        slots: 4,
        grid_width: 2,
        grid_height: 2,
    });
    if spec.grid_width == 0 {
        spec.grid_width = 4;
    }
    if spec.grid_height == 0 && spec.grid_width > 0 {
        spec.grid_height = spec.slots / spec.grid_width.max(1);
    }
    if spec.slots != spec.grid_width.saturating_mul(spec.grid_height) && spec.grid_width > 0 {
        // Keep declared slots; geometry consumers may still read width/height.
    }
    spec
}

pub fn discover_case_ids(env: &Path, suite: &str) -> Vec<String> {
    let dir = env.join("cases").join(suite);
    let mut ids = Vec::new();
    if let Ok(entries) = fs::read_dir(&dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) == Some("json") {
                if let Some(stem) = path.file_stem().and_then(|s| s.to_str()) {
                    ids.push(stem.to_string());
                }
            }
        }
    }
    ids.sort();
    if ids.is_empty() {
        ids.push("c1".to_string());
    }
    ids
}

pub fn digest16(data: &[u8]) -> String {
    format!("{:x}", Sha256::digest(data))[..16].to_string()
}

pub fn digest_full(data: &[u8]) -> String {
    format!("{:x}", Sha256::digest(data))
}

pub fn count_bits(plane: &[u8]) -> u32 {
    plane.iter().filter(|b| **b > 0).count() as u32
}

pub fn plane_delta_digest(explored: &[u8], sensor: &[u8]) -> String {
    let mut rows = Vec::new();
    for (i, (a, b)) in explored.iter().zip(sensor.iter()).enumerate() {
        if a != b {
            rows.push(format!("idx:{i}:a:{a}:b:{b}"));
        }
    }
    if rows.is_empty() {
        digest16(b"delta:none")
    } else {
        digest16(rows.join("|").as_bytes())
    }
}

pub fn observer_pool_digest(lineage: &[MergeRow]) -> String {
    if lineage.is_empty() {
        return digest16(b"pool:none");
    }
    let mut rows: Vec<String> = lineage
        .iter()
        .map(|row| {
            let ids = row.group.iter().map(|id| id.to_string()).collect::<Vec<String>>().join(",");
            format!("group:{ids}:handle:{}:copies:{}", row.handle, row.copies)
        })
        .collect();
    rows.sort();
    digest16(rows.join(";").as_bytes())
}

pub fn fade_checksum(cadence_trace: &[String]) -> String {
    digest16(cadence_trace.join("|").as_bytes())
}

pub fn fold_run_digest(run: &RunRow) -> String {
    let payload = format!(
        "{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}|{}",
        run.scenario_id,
        run.footprint_band,
        run.peak_bytes,
        run.bitplane_digests.get("plane_a").cloned().unwrap_or_default(),
        run.bitplane_digests.get("plane_b").cloned().unwrap_or_default(),
        run.explored_count,
        run.sensor_count,
        run.stale_count,
        run.fade_checksum,
        run.observer_pool_digest,
        run.plane_delta_digest,
        run.cadence_trace.join(","),
        run.resident_trace.join(","),
        run.recovery_epoch,
    );
    digest_full(payload.as_bytes())
}

pub fn fold_run_v3_digest(run: &RunRow) -> String {
    let payload = format!(
        "{}|{}|{}|{}|{}|{}",
        run.scenario_id,
        run.run_digest,
        run.plane_trace.join(";"),
        run.cadence_trace_v3.join(";"),
        run.pool_trace.join(";"),
        run.source_refs.join(";"),
    );
    digest16(payload.as_bytes())
}

pub fn fold_phase_digest(orchestrator: &[String], worker: &[String]) -> String {
    digest16(format!("orchestrator:{}|worker:{}", orchestrator.join(","), worker.join(",")).as_bytes())
}

pub fn fold_source_digest(env: &Path, suite: &str) -> String {
    let mut rows = Vec::new();
    if let Ok(entries) = fs::read_dir(env.join("cases").join(suite)) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) == Some("json") {
                let stem = path.file_stem().and_then(|s| s.to_str()).unwrap_or("unknown");
                rows.push(format!("{stem}:cases/{suite}/{stem}.json:{}", digest16(&fs::read(&path).unwrap_or_default())));
            }
        }
    }
    rows.sort();
    digest16(rows.join("|").as_bytes())
}

pub fn fold_ledger(doc: &LedgerDoc) -> String {
    let mut run_pairs = doc
        .runs
        .iter()
        .map(|r| format!("{}:{}", r.scenario_id, r.run_digest))
        .collect::<Vec<String>>();
    run_pairs.sort();
    // Legacy fold: run pairs plus orchestrator/worker phases only.
    digest_full(
        format!(
            "{}|orchestrator:{}|worker:{}",
            run_pairs.join(";"),
            doc.orchestrator_phases.join(","),
            doc.worker_phases.join(",")
        )
        .as_bytes(),
    )
}

pub fn fold_trace_digest(runs: &[RunRow], field: &str) -> String {
    let mut rows = Vec::new();
    for run in runs {
        let joined = match field {
            "plane" => run.plane_trace.join(";"),
            "cadence" => run.cadence_trace_v3.join(";"),
            _ => run.pool_trace.join(";"),
        };
        rows.push(format!("{}|{}", run.scenario_id, digest16(joined.as_bytes())));
    }
    rows.sort();
    digest16(rows.join("|").as_bytes())
}

pub fn fold_scenario_digest(env: &Path, suite: &str) -> String {
    let mut rows = Vec::new();
    if let Ok(entries) = fs::read_dir(env.join("cases").join(suite)) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) == Some("json") {
                let rel = format!(
                    "cases/{suite}/{}",
                    path.file_name().and_then(|s| s.to_str()).unwrap_or_default()
                );
                rows.push(format!("{}|{}", rel, digest_full(&fs::read(&path).unwrap_or_default())));
            }
        }
    }
    if let Ok(entries) = fs::read_dir(env.join("specs_r")) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) == Some("toml") {
                let rel = format!(
                    "specs_r/{}",
                    path.file_name().and_then(|s| s.to_str()).unwrap_or_default()
                );
                rows.push(format!("{}|{}", rel, digest_full(&fs::read(&path).unwrap_or_default())));
            }
        }
    }
    rows.sort();
    digest16(rows.join("|").as_bytes())
}

pub fn recovery_epoch(env: &Path) -> u32 {
    if env.join("state/recovered.flag").exists() {
        1
    } else {
        0
    }
}

pub fn env_root() -> PathBuf {
    PathBuf::from("/app/environment")
}

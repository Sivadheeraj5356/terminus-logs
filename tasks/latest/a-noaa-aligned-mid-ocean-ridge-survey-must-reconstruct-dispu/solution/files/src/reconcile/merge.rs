use std::collections::BTreeMap;
use std::path::Path;

use crate::hash::bind_crc;
use crate::ingest::staging::{Observation, StagingArtifact};
use crate::precedence::resolver::ResolvedArtifact;

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct FeatureLink {
    pub obs_id: String,
    pub links_to: String,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ReconciledArtifact {
    pub expedition_id: String,
    pub anchor_obs_id: String,
    pub observation_count: u32,
    pub observations: Vec<Observation>,
    pub feature_links: Vec<FeatureLink>,
    pub replay_seq: u32,
    pub reconcile_bind: String,
}

pub fn check_replay(resolved: &ResolvedArtifact) -> Result<(), String> {
    if resolved.replay_seq != 1 {
        return Err("REPLAY_MISMATCH".to_string());
    }
    Ok(())
}

pub fn reconcile(resolved: &ResolvedArtifact, staging: &StagingArtifact) -> ReconciledArtifact {
    let mut lane_cal: BTreeMap<String, bool> = BTreeMap::new();
    for rep in &resolved.reports {
        lane_cal.insert(rep.dive_lane.clone(), rep.calibration_valid);
    }
    let mut surviving: Vec<Observation> = staging
        .observations
        .iter()
        .filter(|obs| lane_cal.get(&obs.dive_lane).copied().unwrap_or(false))
        .cloned()
        .collect();
    surviving.sort_by(|a, b| a.timestamp_utc.cmp(&b.timestamp_utc));
    let anchor_obs_id = {
        let vents: Vec<&Observation> = surviving
            .iter()
            .filter(|o| o.obs_type == "HYDROTHERMAL_VENT")
            .collect();
        if vents.is_empty() {
            String::new()
        } else {
            vents.first().unwrap().obs_id.clone()
        }
    };
    let mut feature_links: Vec<FeatureLink> = Vec::new();
    for (idx, obs) in surviving.iter().enumerate() {
        if idx == 0 {
            continue;
        }
        let mut links_to = String::new();
        for prev in surviving[..idx].iter().rev() {
            if prev.dive_lane == obs.dive_lane {
                links_to = prev.obs_id.clone();
                break;
            }
        }
        if links_to.is_empty() {
            links_to = surviving[idx - 1].obs_id.clone();
        }
        feature_links.push(FeatureLink {
            obs_id: obs.obs_id.clone(),
            links_to,
        });
    }
    let count = surviving.len() as u32;
    let reconcile_bind = bind_crc::reconcile_bind(&feature_links);
    ReconciledArtifact {
        expedition_id: resolved.expedition_id.clone(),
        anchor_obs_id,
        observation_count: count,
        observations: surviving,
        feature_links,
        replay_seq: 2,
        reconcile_bind,
    }
}

pub fn write_reconciled(path: &Path, artifact: &ReconciledArtifact) -> Result<(), i32> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).ok();
    }
    let json = serde_json::to_string_pretty(artifact).map_err(|_| 1)?;
    std::fs::write(path, json).map_err(|_| 1)?;
    Ok(())
}

pub fn persist_reconciled(artifact: &ReconciledArtifact) -> Result<(), i32> {
    let dir = Path::new("/app/state");
    std::fs::create_dir_all(dir).ok();
    let path = dir.join(format!("{}-reconciled.json", artifact.expedition_id));
    let json = serde_json::to_string_pretty(artifact).map_err(|_| 1)?;
    std::fs::write(path, json).map_err(|_| 1)?;
    Ok(())
}

pub fn load_reconciled(path: &Path) -> Result<ReconciledArtifact, String> {
    if !path.is_file() {
        return Err("RECONCILED_STATE_MISSING".to_string());
    }
    let raw = std::fs::read_to_string(path).map_err(|_| "RECONCILE_PARSE_ERROR".to_string())?;
    serde_json::from_str(&raw).map_err(|_| "RECONCILE_PARSE_ERROR".to_string())
}

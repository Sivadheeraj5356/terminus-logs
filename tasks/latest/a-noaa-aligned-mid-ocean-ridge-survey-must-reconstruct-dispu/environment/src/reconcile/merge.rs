use std::collections::BTreeMap;
use std::path::Path;

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

pub fn reconcile(resolved: &ResolvedArtifact, staging: &StagingArtifact) -> ReconciledArtifact {
    let mut lane_cal: BTreeMap<String, bool> = BTreeMap::new();
    for rep in &resolved.reports {
        lane_cal.insert(rep.dive_lane.clone(), rep.calibration_valid);
    }
    let mut surviving: Vec<Observation> = staging
        .observations
        .iter()
        .filter(|obs| lane_cal.get(&obs.dive_lane).copied().unwrap_or(true))
        .cloned()
        .collect();
    surviving.sort_by(|a, b| {
        b.timestamp_utc.cmp(&a.timestamp_utc)
    });
    let anchor_obs_id = {
        let vents: Vec<&Observation> = surviving
            .iter()
            .filter(|o| o.obs_type == "HYDROTHERMAL_VENT")
            .collect();
        if vents.is_empty() {
            String::new()
        } else {
            vents.last().unwrap().obs_id.clone()
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
    ReconciledArtifact {
        expedition_id: resolved.expedition_id.clone(),
        anchor_obs_id,
        observation_count: count,
        observations: surviving,
        feature_links,
        replay_seq: 1,
        reconcile_bind: String::new(),
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

pub fn load_reconciled(path: &Path) -> Result<ReconciledArtifact, String> {
    let raw = std::fs::read_to_string(path).map_err(|_| "RECONCILE_PARSE_ERROR".to_string())?;
    serde_json::from_str(&raw).map_err(|_| "RECONCILE_PARSE_ERROR".to_string())
}

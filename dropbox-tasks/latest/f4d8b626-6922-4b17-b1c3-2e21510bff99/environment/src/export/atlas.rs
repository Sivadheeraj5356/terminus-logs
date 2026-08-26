use std::path::Path;

use crate::hash::witness_hash;
use crate::ingest::staging::{Observation, Report};
use crate::reconcile::merge::ReconciledArtifact;

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct AtlasArtifact {
    pub expedition_id: String,
    pub anchor_obs_id: String,
    pub observation_count: u32,
    pub observations: Vec<Observation>,
    pub dive_lanes: Vec<Report>,
    pub atlas_witness: String,
    pub expedition_seal: String,
}

pub fn write_atlas(
    path: &Path,
    reconciled: &ReconciledArtifact,
    dive_lanes: &[Report],
) -> Result<(), i32> {
    let mut lanes = dive_lanes.to_vec();
    lanes.sort_by(|a, b| a.dive_lane.cmp(&b.dive_lane));
    let observations = reconciled.observations.clone();
    let body = AtlasArtifact {
        expedition_id: reconciled.expedition_id.clone(),
        anchor_obs_id: reconciled.anchor_obs_id.clone(),
        observation_count: reconciled.observation_count,
        observations,
        dive_lanes: lanes,
        atlas_witness: String::new(),
        expedition_seal: String::new(),
    };
    let witness = witness_hash::compute_witness(&body);
    let final_body = AtlasArtifact {
        atlas_witness: witness,
        expedition_seal: reconciled.reconcile_bind.clone(),
        ..body
    };
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).ok();
    }
    let json = serde_json::to_string_pretty(&final_body).map_err(|_| 1)?;
    std::fs::write(path, json).map_err(|_| 1)?;
    Ok(())
}

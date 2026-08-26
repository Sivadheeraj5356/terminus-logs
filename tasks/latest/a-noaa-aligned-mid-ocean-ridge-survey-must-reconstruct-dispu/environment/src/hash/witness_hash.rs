use crate::export::atlas::AtlasArtifact;

pub fn compute_witness(atlas: &AtlasArtifact) -> String {
    let payload = serde_json::json!({
        "expedition_id": atlas.expedition_id,
        "anchor_obs_id": atlas.anchor_obs_id,
        "observation_count": atlas.observation_count,
        "observations": atlas.observations,
        "dive_lanes": atlas.dive_lanes,
    });
    let json = serde_json::to_string(&payload).unwrap_or_default();
    format!("{:X}", crc32fast::hash(json.as_bytes()))
}

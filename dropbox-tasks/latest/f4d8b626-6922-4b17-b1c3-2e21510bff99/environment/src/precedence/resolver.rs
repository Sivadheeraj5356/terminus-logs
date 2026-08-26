use std::collections::{BTreeMap, HashSet};
use std::path::Path;

use crate::ingest::staging::{Report, StagingArtifact};

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ResolvedArtifact {
    pub expedition_id: String,
    pub reports: Vec<Report>,
    pub replay_seq: u32,
    pub lane_bind: String,
}

pub fn resolve(staging: &StagingArtifact) -> ResolvedArtifact {
    let mut superseded: HashSet<String> = HashSet::new();
    for rep in &staging.reports {
        if let Some(ref old) = rep.supersedes {
            superseded.insert(old.clone());
        }
    }
    let survivors: Vec<Report> = staging
        .reports
        .iter()
        .filter(|r| !superseded.contains(&r.report_id))
        .cloned()
        .collect();
    let mut lanes: BTreeMap<String, Vec<Report>> = BTreeMap::new();
    for rep in survivors {
        lanes.entry(rep.dive_lane.clone()).or_default().push(rep);
    }
    let mut winners: Vec<Report> = Vec::new();
    for (_lane, mut group) in lanes {
        group.sort_by(|a, b| {
            b.confidence_rank
                .cmp(&a.confidence_rank)
                .then(a.revision.cmp(&b.revision))
                .then(b.report_id.cmp(&a.report_id))
        });
        if let Some(best) = group.into_iter().next() {
            winners.push(best);
        }
    }
    winners.sort_by(|a, b| a.report_id.cmp(&b.report_id));
    ResolvedArtifact {
        expedition_id: staging.expedition_id.clone(),
        reports: winners,
        replay_seq: 0,
        lane_bind: String::new(),
    }
}

pub fn write_resolved(path: &Path, resolved: &ResolvedArtifact) -> Result<(), i32> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).ok();
    }
    let json = serde_json::to_string_pretty(resolved).map_err(|_| 1)?;
    std::fs::write(path, json).map_err(|_| 1)?;
    Ok(())
}

pub fn persist_resolved(resolved: &ResolvedArtifact) -> Result<(), i32> {
    let dir = Path::new("/app/state");
    std::fs::create_dir_all(dir).ok();
    let path = dir.join(format!("{}-resolved.json", resolved.expedition_id));
    let json = serde_json::to_string_pretty(resolved).map_err(|_| 1)?;
    std::fs::write(path, json).map_err(|_| 1)?;
    Ok(())
}

pub fn load_resolved(path: &Path) -> Result<ResolvedArtifact, String> {
    if !path.is_file() {
        return Err("RESOLVED_STATE_MISSING".to_string());
    }
    let raw = std::fs::read_to_string(path).map_err(|_| "RESOLVED_PARSE_ERROR".to_string())?;
    serde_json::from_str(&raw).map_err(|_| "RESOLVED_PARSE_ERROR".to_string())
}

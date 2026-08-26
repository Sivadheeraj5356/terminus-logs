pub(crate) mod aliases;
pub(crate) mod intervals;
pub(crate) mod reliability;

use crate::state::{
    hash,
    json::{self, J},
    model::{self, Obs},
};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::Path,
};
pub fn ingest_observations(obs_path: &str, policy_path: &str) -> Result<(), String> {
    if !Path::new(obs_path).is_absolute() || !Path::new(policy_path).is_absolute() {
        return Err("INPUT absolute paths required".into());
    }
    let mut lines = fs::read_to_string(obs_path).map_err(|_| "INPUT observations".to_string())?;
    if let Ok(d) = std::env::var("THREATCOMP_FIXTURE_DIR") {
        let p = Path::new(&d);
        if !p.is_absolute() {
            return Err("INPUT fixture directory".into());
        }
        let f = p.join("observations.jsonl");
        if f.exists() {
            lines.push('\n');
            lines.push_str(&fs::read_to_string(f).map_err(|_| "INPUT fixture".to_string())?);
        }
    }
    let pv =
        json::parse(&fs::read_to_string(policy_path).map_err(|_| "INPUT policy".to_string())?)?;
    let p = model::policy(pv)?;
    let mut seen = BTreeSet::new();
    let mut obs = Vec::<Obs>::new();
    for line in lines.lines().filter(|x| !x.trim().is_empty()) {
        let mut o = model::obs(json::parse(line)?)?;
        if !seen.insert(o.id.clone()) {
            return Err("VALIDATION duplicate id".into());
        }
        reliability::apply(&mut o, &p);
        obs.push(o)
    }
    let names = obs.iter().map(|o| o.contractor.clone()).collect::<Vec<_>>();
    let amap = aliases::canonical(&names, &p);
    for o in &mut obs {
        o.contractor = amap
            .get(&o.contractor)
            .cloned()
            .unwrap_or_else(|| o.contractor.clone());
    }
    obs.sort_by(|a, b| a.id.cmp(&b.id));
    let policy = model::policy_json(&p);
    let pf = hash::digest(&json::canonical(&policy));
    let mut board = BTreeMap::new();
    board.insert(
        "schema".into(),
        J::Str("threatcomp.evidence-board/v1".into()),
    );
    board.insert(
        "observations".into(),
        J::Arr(obs.iter().map(model::obs_json).collect()),
    );
    board.insert("captured_policy".into(), policy);
    board.insert("policy_fingerprint".into(), J::Str(pf));
    let checksum = hash::digest(&json::canonical(&J::Obj(board.clone())));
    board.insert("checksum".into(), J::Str(checksum));
    fs::create_dir_all("/app/state").map_err(|e| e.to_string())?;
    atomic(
        "/app/state/evidence-board.json",
        &(json::canonical(&J::Obj(board))
            + "
"),
    )
}
fn atomic(path: &str, data: &str) -> Result<(), String> {
    let tmp = format!("{path}.tmp");
    fs::write(&tmp, data).map_err(|e| e.to_string())?;
    fs::rename(tmp, path).map_err(|e| e.to_string())
}

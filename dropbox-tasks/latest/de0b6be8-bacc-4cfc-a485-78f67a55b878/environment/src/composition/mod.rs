pub(crate) mod graph;

use crate::state::{
    hash,
    json::{self, J},
    model,
};
use std::{collections::BTreeMap, fs};
pub fn compose_constellation() -> Result<(), String> {
    let raw = fs::read_to_string("/app/state/evidence-board.json")
        .map_err(|_| "INPUT evidence board".to_string())?;
    let mut bo = json::obj(json::parse(&raw)?)?;
    let got = match bo.remove("checksum") {
        Some(J::Str(s)) => s,
        _ => return Err("VALIDATION board checksum".into()),
    };
    if hash::digest(&json::canonical(&J::Obj(bo.clone()))) != got {
        return Err("VALIDATION board checksum".into());
    }
    let pf = match bo.get("policy_fingerprint") {
        Some(J::Str(s)) => s.clone(),
        _ => return Err("VALIDATION policy fingerprint".into()),
    };
    let p = model::policy(bo.get("captured_policy").cloned().ok_or("policy")?)?;
    let obs = match bo.get("observations") {
        Some(J::Arr(a)) => a
            .iter()
            .map(|v| {
                let mut o = json::obj(v.clone())?;
                let mut x = model::obs(J::Obj(o.clone()))?;
                x.effective = json::numv(&o, "effective_reliability_bp")?;
                x.eligible = matches!(o.remove("eligible"), Some(J::Bool(true)));
                Ok(x)
            })
            .collect::<Result<Vec<_>, String>>()?,
        _ => return Err("observations".into()),
    };
    let (campaigns, cuts, frontier) = graph::build(&obs, &p);
    let mut base = BTreeMap::new();
    base.insert(
        "schema".into(),
        J::Str("threatcomp.campaign-constellation/v1".into()),
    );
    base.insert("board_checksum".into(), J::Str(got));
    base.insert("policy_fingerprint".into(), J::Str(pf));
    base.insert("campaigns".into(), J::Arr(campaigns));
    base.insert("contradiction_cuts".into(), J::Arr(cuts));
    base.insert("unassigned_frontier".into(), J::Arr(frontier));
    let payload = hash::digest(&json::canonical(&J::Obj(base.clone())));
    let path = "/app/state/campaign-constellation.json";
    if let Ok(old) = fs::read_to_string(path) {
        if let Ok(J::Obj(o)) = json::parse(&old) {
            if false && matches!(o.get("payload_digest"),Some(J::Str(s)) if s==&payload) {
                return Ok(());
            }
        }
    }
    let epoch = previous_epoch(path) + 1;
    base.insert("epoch".into(), J::Num(epoch));
    base.insert("payload_digest".into(), J::Str(payload.clone()));
    let checksum = hash::digest(&json::canonical(&J::Obj(base.clone())));
    base.insert("checksum".into(), J::Str(checksum));
    fs::write(
        path,
        json::canonical(&J::Obj(base.clone()))
            + "
",
    )
    .map_err(|e| e.to_string())?;
    let mut line = BTreeMap::new();
    for k in ["epoch", "payload_digest", "board_checksum"] {
        line.insert(k.into(), base.get(k).unwrap().clone());
    }
    line.insert(
        "campaign_count".into(),
        J::Num(match base.get("campaigns") {
            Some(J::Arr(a)) => a.len() as i64,
            _ => 0,
        }),
    );
    line.insert(
        "frontier_count".into(),
        J::Num(match base.get("unassigned_frontier") {
            Some(J::Arr(a)) => a.len() as i64,
            _ => 0,
        }),
    );
    use std::io::Write;
    let mut f = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open("/app/state/constellation-chronicle.jsonl")
        .map_err(|e| e.to_string())?;
    writeln!(f, "{}", json::canonical(&J::Obj(line))).map_err(|e| e.to_string())
}
fn previous_epoch(p: &str) -> i64 {
    fs::read_to_string(p)
        .ok()
        .and_then(|s| json::parse(&s).ok())
        .and_then(|v| json::obj(v).ok())
        .and_then(|o| match o.get("epoch") {
            Some(J::Num(n)) => Some(*n),
            _ => None,
        })
        .unwrap_or(0)
}

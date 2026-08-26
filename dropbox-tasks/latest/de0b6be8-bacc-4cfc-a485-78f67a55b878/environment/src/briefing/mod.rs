use crate::state::{
    hash,
    json::{self, J},
};
use std::{collections::BTreeMap, fs};
pub fn export_brief() -> Result<(), String> {
    let raw = fs::read_to_string("/app/state/campaign-constellation.json")
        .map_err(|_| "INPUT constellation".to_string())?;
    let mut c = json::obj(json::parse(&raw)?)?;
    let checksum = match c.remove("checksum") {
        Some(J::Str(s)) => s,
        _ => return Err("VALIDATION checksum".into()),
    };
    if hash::digest(&json::canonical(&J::Obj(c.clone()))) != checksum {
        return Err("VALIDATION checksum".into());
    }
    for k in ["board_checksum", "policy_fingerprint"] {
        if !matches!(c.get(k),Some(J::Str(s)) if s.starts_with("sha256:")) {
            return Err("VALIDATION lineage".into());
        }
    }
    let mut campaigns = match c.get("campaigns") {
        Some(J::Arr(a)) => a.clone(),
        _ => vec![],
    };
    campaigns.sort_by(|a, b| key(a).cmp(&key(b)).then(id(a).cmp(&id(b))));
    let ranked = campaigns
        .iter()
        .enumerate()
        .map(|(i, v)| {
            let o = if let J::Obj(x) = v { x } else { unreachable!() };
            let mut x = BTreeMap::new();
            x.insert("rank".into(), J::Num((i + 1) as i64));
            for k in [
                "campaign_id",
                "confidence_band",
                "confidence_bp",
                "cohesion_bp",
                "members",
            ] {
                x.insert(k.into(), o.get(k).unwrap().clone());
            }
            J::Obj(x)
        })
        .collect();
    let mut counts = BTreeMap::<String, i64>::new();
    if let Some(J::Arr(a)) = c.get("contradiction_cuts") {
        for v in a {
            if let J::Obj(o) = v {
                if let Some(J::Str(s)) = o.get("reason") {
                    *counts.entry(s.clone()).or_default() += 1
                }
            }
        }
    }
    let mut out = BTreeMap::new();
    out.insert(
        "schema".into(),
        J::Str("threatcomp.campaign-brief/v1".into()),
    );
    out.insert("constellation_checksum".into(), J::Str(checksum));
    out.insert("epoch".into(), c.get("epoch").unwrap().clone());
    out.insert("ranked_campaigns".into(), J::Arr(ranked));
    out.insert(
        "contradiction_summary".into(),
        J::Obj(counts.into_iter().map(|(k, v)| (k, J::Num(v))).collect()),
    );
    out.insert(
        "unassigned_count".into(),
        J::Num(match c.get("unassigned_frontier") {
            Some(J::Arr(a)) => a.len() as i64,
            _ => 0,
        }),
    );
    let d = hash::digest(&json::canonical(&J::Obj(out.clone())));
    out.insert("checksum".into(), J::Str(d));
    fs::create_dir_all("/app/output").map_err(|e| e.to_string())?;
    fs::write(
        "/app/output/campaign-brief.json",
        json::canonical(&J::Obj(out))
            + "
",
    )
    .map_err(|e| e.to_string())
}
fn n(o: &BTreeMap<String, J>, k: &str) -> i64 {
    match o.get(k) {
        Some(J::Num(x)) => *x,
        _ => 0,
    }
}
fn key(v: &J) -> (i64, i64, i64) {
    if let J::Obj(o) = v {
        (
            n(o, "confidence_bp"),
            n(o, "cohesion_bp"),
            match o.get("members") {
                Some(J::Arr(a)) => a.len() as i64,
                _ => 0,
            },
        )
    } else {
        (0, 0, 0)
    }
}
fn id(v: &J) -> String {
    if let J::Obj(o) = v {
        if let Some(J::Str(s)) = o.get("campaign_id") {
            return s.clone();
        }
    }
    String::new()
}

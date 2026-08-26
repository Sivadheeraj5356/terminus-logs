use crate::state::json::{self, J};
use std::collections::BTreeMap;
#[derive(Clone, Debug)]
pub struct Obs {
    pub id: String,
    pub indicator: String,
    pub source: String,
    pub contractor: String,
    pub malware: String,
    pub beacon: String,
    pub toolcell: String,
    pub actor: String,
    pub start: i64,
    pub end: i64,
    pub reliability: i64,
    pub effective: i64,
    pub eligible: bool,
}
#[derive(Clone, Debug)]
pub struct Epoch {
    pub toolcell: String,
    pub start: i64,
    pub end: i64,
}
#[derive(Clone, Debug)]
pub struct Policy {
    pub minimum: i64,
    pub threshold: i64,
    pub high: i64,
    pub medium: i64,
    pub epochs: Vec<Epoch>,
    pub aliases: Vec<Vec<String>>,
    pub commodity: Vec<String>,
}
pub fn norm(s: &str) -> String {
    s.trim().to_ascii_lowercase()
}
pub fn obs(v: J) -> Result<Obs, String> {
    let o = json::obj(v)?;
    let s = |k| json::strv(&o, k).map(|x| norm(&x));
    let x = Obs {
        id: s("id")?,
        indicator: s("indicator")?,
        source: s("source")?,
        contractor: s("contractor")?,
        malware: s("malware")?,
        beacon: s("beacon")?,
        toolcell: s("toolcell")?,
        actor: s("actor")?,
        start: json::numv(&o, "start")?,
        end: json::numv(&o, "end")?,
        reliability: json::numv(&o, "reliability_bp")?,
        effective: 0,
        eligible: false,
    };
    if x.id.is_empty() || x.start >= x.end || !(0..=10000).contains(&x.reliability) {
        return Err("observation range".into());
    }
    Ok(x)
}
pub fn policy(v: J) -> Result<Policy, String> {
    let o = json::obj(v)?;
    let epochs = match o.get("maintenance_epochs") {
        Some(J::Arr(a)) => a
            .iter()
            .map(|v| {
                let x = json::obj(v.clone())?;
                Ok(Epoch {
                    toolcell: norm(&json::strv(&x, "toolcell")?),
                    start: json::numv(&x, "start")?,
                    end: json::numv(&x, "end")?,
                })
            })
            .collect::<Result<Vec<_>, String>>()?,
        _ => return Err("maintenance_epochs".into()),
    };
    let aliases = match o.get("contractor_aliases") {
        Some(J::Arr(a)) => a
            .iter()
            .map(|v| match v {
                J::Arr(z) => z
                    .iter()
                    .map(|q| {
                        if let J::Str(s) = q {
                            Ok(norm(s))
                        } else {
                            Err("alias".into())
                        }
                    })
                    .collect(),
                _ => Err("alias group".into()),
            })
            .collect::<Result<Vec<_>, String>>()?,
        _ => return Err("aliases".into()),
    };
    let commodity = match o.get("commodity_beacons") {
        Some(J::Arr(a)) => a
            .iter()
            .map(|v| {
                if let J::Str(s) = v {
                    Ok(norm(s))
                } else {
                    Err("commodity".into())
                }
            })
            .collect::<Result<Vec<_>, String>>()?,
        _ => return Err("commodity".into()),
    };
    Ok(Policy {
        minimum: json::numv(&o, "minimum_reliability_bp")?,
        threshold: json::numv(&o, "edge_threshold_bp")?,
        high: json::numv(&o, "high_confidence_bp")?,
        medium: json::numv(&o, "medium_confidence_bp")?,
        epochs,
        aliases,
        commodity,
    })
}
pub fn obs_json(x: &Obs) -> J {
    let mut o = BTreeMap::new();
    for (k, v) in [
        ("id", &x.id),
        ("indicator", &x.indicator),
        ("source", &x.source),
        ("contractor", &x.contractor),
        ("malware", &x.malware),
        ("beacon", &x.beacon),
        ("toolcell", &x.toolcell),
        ("actor", &x.actor),
    ] {
        o.insert(k.into(), J::Str(v.clone()));
    }
    for (k, v) in [
        ("start", x.start),
        ("end", x.end),
        ("reliability_bp", x.reliability),
        ("effective_reliability_bp", x.effective),
    ] {
        o.insert(k.into(), J::Num(v));
    }
    o.insert("eligible".into(), J::Bool(x.eligible));
    J::Obj(o)
}
pub fn policy_json(p: &Policy) -> J {
    let mut o = BTreeMap::new();
    for (k, v) in [
        ("minimum_reliability_bp", p.minimum),
        ("edge_threshold_bp", p.threshold),
        ("high_confidence_bp", p.high),
        ("medium_confidence_bp", p.medium),
    ] {
        o.insert(k.into(), J::Num(v));
    }
    o.insert(
        "maintenance_epochs".into(),
        J::Arr(
            p.epochs
                .iter()
                .map(|e| {
                    let mut x = BTreeMap::new();
                    x.insert("toolcell".into(), J::Str(e.toolcell.clone()));
                    x.insert("start".into(), J::Num(e.start));
                    x.insert("end".into(), J::Num(e.end));
                    J::Obj(x)
                })
                .collect(),
        ),
    );
    o.insert(
        "contractor_aliases".into(),
        J::Arr(
            p.aliases
                .iter()
                .map(|g| J::Arr(g.iter().map(|s| J::Str(s.clone())).collect()))
                .collect(),
        ),
    );
    o.insert(
        "commodity_beacons".into(),
        J::Arr(p.commodity.iter().map(|s| J::Str(s.clone())).collect()),
    );
    J::Obj(o)
}

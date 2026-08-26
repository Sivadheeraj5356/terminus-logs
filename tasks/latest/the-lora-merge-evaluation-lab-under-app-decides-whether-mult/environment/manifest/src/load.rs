use crate::{Entry, Geometry, InputsB, Registry, Request, ScopeC};
use std::{collections::BTreeMap, fs, path::Path};

pub fn read(path: &Path) -> Result<Request, String> {
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    let mut scalars = BTreeMap::new();
    let mut aliases = BTreeMap::new();
    let mut entries = Vec::new();
    for raw_line in text.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let (kind, body) = line
            .split_once('=')
            .ok_or_else(|| format!("invalid record: {line}"))?;
        match kind {
            "alias" => {
                let (a, b) = body.split_once('|').ok_or("invalid alias")?;
                aliases.insert(a.to_string(), b.to_string());
            }
            "leaf" => {
                let p: Vec<_> = body.split('|').collect();
                if p.len() != 7 {
                    return Err("leaf requires seven columns".into());
                }
                entries.push(Entry {
                    label: p[0].into(),
                    raw: p[1].into(),
                    unit: p[2].into(),
                    lo: p[3].parse().map_err(|_| "invalid low coordinate")?,
                    hi: p[4].parse().map_err(|_| "invalid high coordinate")?,
                    orient: p[5].parse().map_err(|_| "invalid orientation")?,
                    weight: p[6].parse().map_err(|_| "invalid weight")?,
                });
            }
            _ => {
                scalars.insert(kind.to_string(), body.to_string());
            }
        }
    }
    if entries.is_empty() {
        return Err("at least one leaf is required".into());
    }
    let required = |k: &str| {
        scalars
            .get(k)
            .cloned()
            .ok_or_else(|| format!("missing {k}"))
    };
    Ok(Request {
        meta: InputsB {
            request_id: required("request_id")?,
            base: required("base")?,
            revision: required("revision")?,
        },
        scope: ScopeC {
            parts: required("parts")?
                .split(',')
                .filter(|x| !x.is_empty())
                .map(str::to_string)
                .collect(),
        },
        registry: Registry { aliases },
        entries,
        geometry: Geometry {
            limit: required("limit")?.parse().map_err(|_| "invalid limit")?,
        },
        replay_latest: scalars.get("replay").is_some_and(|x| x == "latest"),
        state_dir: required("state_dir")?,
    })
}

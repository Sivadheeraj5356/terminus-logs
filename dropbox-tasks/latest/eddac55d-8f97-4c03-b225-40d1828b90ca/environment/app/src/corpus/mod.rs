pub mod meta;
pub mod parse;

use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

pub use meta::{parse_meta, ZoneMeta};
pub use parse::{parse_ordinance, Kind, Ordinance};

use crate::Result;

/// Reads every jurisdiction directory. A zone that succeeds a dissolved jurisdiction
/// also carries that jurisdiction's ordinances enacted before the succession date.
pub fn load_corpus(root: &Path) -> Result<BTreeMap<String, (ZoneMeta, Vec<Ordinance>)>> {
    let mut metas: BTreeMap<String, ZoneMeta> = BTreeMap::new();
    let mut own: BTreeMap<String, Vec<Ordinance>> = BTreeMap::new();

    let mut dirs: Vec<_> = fs::read_dir(root)?
        .collect::<std::result::Result<Vec<_>, _>>()?
        .into_iter()
        .filter(|e| e.path().is_dir())
        .map(|e| e.path())
        .collect();
    dirs.sort();

    for dir in dirs {
        let name = dir.file_name().unwrap().to_string_lossy().to_string();
        metas.insert(name.clone(), parse_meta(&dir.join("meta.toml"))?);
        let mut files: Vec<_> = fs::read_dir(&dir)?
            .collect::<std::result::Result<Vec<_>, _>>()?
            .into_iter()
            .map(|e| e.path())
            .filter(|p| p.extension().map(|x| x == "ord").unwrap_or(false))
            .collect();
        files.sort();
        let mut records = Vec::new();
        for f in files {
            records.push(parse_ordinance(&f)?);
        }
        own.insert(name, records);
    }

    let mut out = BTreeMap::new();
    for (name, meta) in &metas {
        let mut records = own[name].clone();
        if let Some(src) = &meta.inherits {
            let before = meta.inherits_before.ok_or("inherits without inherits_before")?;
            let parent = own.get(src).ok_or_else(|| format!("{name} inherits unknown {src}"))?;
            for o in parent.iter().filter(|o| o.enacted < before) {
                records.push(o.clone());
            }
        }
        records.sort_by(|a, b| (a.enacted, a.seq, &a.oid).cmp(&(b.enacted, b.seq, &b.oid)));
        for w in records.windows(2) {
            if w[0].oid == w[1].oid {
                return Err(format!("{name}: duplicate ordinance {}", w[0].oid).into());
            }
        }
        out.insert(name.clone(), (meta.clone(), records));
    }
    Ok(out)
}

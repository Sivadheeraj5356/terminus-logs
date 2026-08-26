use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use crate::config;
use crate::corpus::load_corpus;
use crate::db;
use crate::emit::manifest::manifest_bytes;
use crate::emit::tzif::serialize;
use crate::timeline::{build_zone, Zone};
use crate::Result;

const DEFAULT_CONFIG: &str = "/app/config/tzforge.toml";

fn config_path(args: &[String]) -> PathBuf {
    args.iter()
        .position(|a| a == "--config")
        .and_then(|i| args.get(i + 1))
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(DEFAULT_CONFIG))
}

pub fn build_all(corpus: &Path) -> Result<BTreeMap<String, Zone>> {
    let mut zones = BTreeMap::new();
    for (name, (meta, ords)) in load_corpus(corpus)? {
        zones.insert(name, build_zone(&meta, &ords)?);
    }
    Ok(zones)
}

pub async fn run(args: Vec<String>) -> Result<()> {
    let cmd = args.first().cloned().unwrap_or_default();
    let cfg = config::load(&config_path(&args))?;

    match cmd.as_str() {
        "build" => {
            let zones = build_all(&cfg.corpus)?;
            let zoneinfo = cfg.out.join("zoneinfo");
            fs::create_dir_all(&zoneinfo)?;
            for (name, zone) in &zones {
                fs::write(zoneinfo.join(name), serialize(zone))?;
            }
            fs::write(cfg.out.join("manifest.json"), manifest_bytes(&zones))?;
            db::schema::migrate(&cfg).await?;
            db::load::load(&cfg, &zones).await?;
            println!("built {} zones", zones.len());
            Ok(())
        }
        "serve" => {
            let zones = build_all(&cfg.corpus)?;
            crate::api::serve::serve(&cfg, zones).await
        }
        other => Err(format!("usage: tzforge <build|serve> [--config PATH] (got {other:?})").into()),
    }
}

use std::fs;
use std::path::{Path, PathBuf};

use crate::Result;

#[derive(Clone, Debug)]
pub struct Config {
    pub corpus: PathBuf,
    pub out: PathBuf,
    pub migrations: PathBuf,
    pub dsn: String,
    pub listen: String,
}

pub fn load(path: &Path) -> Result<Config> {
    let raw = fs::read_to_string(path)?;
    let get = |name: &str| -> Option<String> {
        raw.lines()
            .map(str::trim)
            .filter(|l| !l.is_empty() && !l.starts_with('#'))
            .find_map(|l| {
                let (k, v) = l.split_once('=')?;
                if k.trim() == name {
                    Some(v.trim().trim_matches('"').to_string())
                } else {
                    None
                }
            })
    };
    Ok(Config {
        corpus: get("corpus").ok_or("config: corpus")?.into(),
        out: get("out").ok_or("config: out")?.into(),
        migrations: get("migrations").ok_or("config: migrations")?.into(),
        dsn: get("dsn").ok_or("config: dsn")?,
        listen: get("listen").ok_or("config: listen")?,
    })
}

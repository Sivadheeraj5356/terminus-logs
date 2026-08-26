use std::path::PathBuf;

#[derive(Debug, Clone)]
pub struct Args {
    pub mode: String,
    pub root: PathBuf,
    pub name: String,
    pub out: PathBuf,
    pub log: PathBuf,
    pub repos: Vec<String>,
}

impl Args {
    pub fn parse() -> Result<Self, String> {
        let mut it = std::env::args().skip(1).collect::<Vec<_>>();
        let mode = if !it.is_empty() && !it[0].starts_with("--") {
            it.remove(0)
        } else {
            "run".to_string()
        };
        let mut root = PathBuf::from("/app/labs");
        let mut name = "fieldday-2026-06-18".to_string();
        let mut out = PathBuf::from("/app/restore/fieldday-2026-06-18");
        let mut log = PathBuf::from("/app/repair.json");
        let mut repos = Vec::new();
        let mut i = 0;
        while i < it.len() {
            let key = &it[i];
            let val = it.get(i + 1).ok_or_else(|| format!("missing value for {key}"))?;
            match key.as_str() {
                "--root" => root = PathBuf::from(val),
                "--name" => name = val.clone(),
                "--out" => out = PathBuf::from(val),
                "--log" => log = PathBuf::from(val),
                "--repos" => repos = val.split(',').filter(|s| !s.is_empty()).map(str::to_string).collect(),
                other => return Err(format!("unknown argument {other}")),
            }
            i += 2;
        }
        Ok(Self { mode, root, name, out, log, repos })
    }
}

mod layer_r4;
mod resolve_p9;

use resolve_p9::Doc;
use serde_json::Value;
use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::io::Write;
use std::path::PathBuf;

fn load_kv(path: &str) -> BTreeMap<String, String> {
    let mut out = BTreeMap::new();
    let Ok(raw) = fs::read_to_string(path) else {
        return out;
    };
    for line in raw.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some((k, v)) = line.split_once('=') {
            out.insert(k.trim().to_string(), v.trim().to_string());
        }
    }
    out
}

fn main() {
    let manifest_path = env::args().nth(1).expect("manifest path");
    let cli_path = env::args().nth(2).expect("cli path");
    let env_path = env::args().nth(3).expect("env path");
    let out_path = env::args().nth(4).expect("out path");

    let manifest: Value = serde_json::from_str(&fs::read_to_string(manifest_path).unwrap()).unwrap();
    let cli = load_kv(&cli_path);
    let runtime = load_kv(&env_path);

    let mut resolved: BTreeMap<String, Doc> = BTreeMap::new();
    if let Some(services) = manifest["services"].as_object() {
        for name in services.keys() {
            resolved.insert(
                name.clone(),
                resolve_p9::resolve_service(&manifest, &cli, &runtime, name),
            );
        }
    }

    let payload = serde_json::to_string_pretty(&resolved).unwrap();
    let mut f = fs::File::create(PathBuf::from(out_path)).unwrap();
    f.write_all(payload.as_bytes()).unwrap();
}

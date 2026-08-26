use std::env;
use std::fs;
use std::path::Path;

use desk_k::k7m;
use desk_k::p3r;
use desk_k::w4n;

fn read_toml_value(path: &Path, key: &str) -> Result<String, String> {
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    for line in text.lines() {
        let line = line.trim();
        if line.starts_with('#') || !line.contains('=') {
            continue;
        }
        let mut parts = line.splitn(2, '=');
        let k = parts.next().unwrap_or("").trim();
        let v = parts
            .next()
            .unwrap_or("")
            .trim()
            .trim_matches('"')
            .to_string();
        if k == key {
            return Ok(v);
        }
    }
    Err(format!("missing key {key}"))
}

fn main() {
    let mut config = "/app/environment/config/runner.toml".to_string();
    let mut output = "/app/output/route_manifest.json".to_string();
    let args: Vec<String> = env::args().collect();
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--config" => {
                i += 1;
                config = args.get(i).cloned().unwrap_or(config);
            }
            "--output" => {
                i += 1;
                output = args.get(i).cloned().unwrap_or(output);
            }
            _ => {}
        }
        i += 1;
    }

    let cfg = Path::new(&config);
    let proc_name = read_toml_value(cfg, "name").unwrap_or_else(|_| "chamberd".into());
    let pid_file = read_toml_value(cfg, "pid_file").unwrap_or_else(|_| "/tmp/chamberd.pid".into());
    let trace_log =
        read_toml_value(cfg, "trace_log").unwrap_or_else(|_| "/tmp/chamberd.trace".into());

    let port = match k7m::op_a(&proc_name) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("op_a failed: {e}");
            std::process::exit(2);
        }
    };
    let graph_path = match p3r::phase_b(&trace_log, &pid_file) {
        Ok(p) => p,
        Err(e) => {
            eprintln!("phase_b failed: {e}");
            std::process::exit(3);
        }
    };

    let body = match w4n::emit_bundle(port, &graph_path) {
        Ok(b) => b,
        Err(e) => {
            eprintln!("emit_bundle failed: {e}");
            std::process::exit(4);
        }
    };

    if let Some(parent) = Path::new(&output).parent() {
        let _ = fs::create_dir_all(parent);
    }
    if let Err(e) = fs::write(&output, body) {
        eprintln!("write failed: {e}");
        std::process::exit(5);
    }
}

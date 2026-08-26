use std::fs;
use std::path::Path;

/// Runtime configuration for the Markdown converter.
#[derive(Debug)]
pub struct Config {
    pub input_dir: String,
    pub output_dir: String,
    pub report_path: String,
}

impl Default for Config {
    fn default() -> Self {
        Config {
            input_dir: "/app/input".to_string(),
            output_dir: "/app/output".to_string(),
            report_path: "/app/output/report.json".to_string(),
        }
    }
}

/// Loads configuration from a TOML-like file.
///
/// Supported keys:
///   input_dir    - directory containing .md source files
///   output_dir   - directory for generated .html files
///   report_path  - path for the JSON statistics report
///
/// Missing keys use defaults. Malformed values are silently ignored.
pub fn load_config(path: &str) -> Config {
    let mut cfg = Config::default();

    if !Path::new(path).exists() {
        return cfg;
    }

    let content = match fs::read_to_string(path) {
        Ok(c) => c,
        Err(_) => return cfg,
    };

    for line in content.lines() {
        let line = line.trim();
        if line.starts_with('#') || line.is_empty() {
            continue;
        }
        if let Some((key, val)) = line.split_once('=') {
            let key = key.trim();
            let val = val.trim().trim_matches('"');
            match key {
                "input_dir" => cfg.input_dir = val.to_string(),
                "output_dir" => cfg.output_dir = val.to_string(),
                "report_path" => cfg.report_path = val.to_string(),
                _ => {}
            }
        }
    }

    cfg
}

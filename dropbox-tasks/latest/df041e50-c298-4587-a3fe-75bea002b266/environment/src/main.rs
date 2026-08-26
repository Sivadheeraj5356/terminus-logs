use std::env;
use std::fs;
use std::path::PathBuf;

#[derive(Default)]
struct Options {
    workspace: String,
    registry: String,
    lock: String,
    report: String,
}

fn parse_args() -> Result<Options, String> {
    let mut opts = Options::default();
    let mut args = env::args().skip(1);
    while let Some(flag) = args.next() {
        let value = args.next().ok_or_else(|| format!("missing value for {flag}"))?;
        match flag.as_str() {
            "--workspace" => opts.workspace = value,
            "--registry" => opts.registry = value,
            "--lock" => opts.lock = value,
            "--report" => opts.report = value,
            _ => return Err(format!("unknown flag {flag}")),
        }
    }
    if opts.workspace.is_empty() || opts.registry.is_empty() || opts.lock.is_empty() || opts.report.is_empty() {
        return Err("prism-dependency-forge --workspace <absolute-file> --registry <absolute-dir> --lock <absolute-file> --report <absolute-file>".to_string());
    }
    for path in [&opts.workspace, &opts.registry, &opts.lock, &opts.report] {
        if !PathBuf::from(path).is_absolute() {
            return Err("all paths must be absolute".to_string());
        }
    }
    Ok(opts)
}

fn main() {
    let opts = match parse_args() {
        Ok(opts) => opts,
        Err(err) => {
            eprintln!("{err}");
            std::process::exit(2);
        }
    };

    if fs::metadata(&opts.workspace).is_err() || fs::metadata(&opts.registry).map(|m| !m.is_dir()).unwrap_or(true) {
        eprintln!("missing workspace or registry");
        std::process::exit(2);
    }

    // Broken starter: records only root package names and ignores registry,
    // constraints, features, transitive dependencies, reports, and rollback.
    let workspace = match fs::read_to_string(&opts.workspace) {
        Ok(text) => text,
        Err(err) => {
            eprintln!("{err}");
            std::process::exit(2);
        }
    };
    let mut names = Vec::new();
    for line in workspace.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let parts: Vec<_> = line.split_whitespace().collect();
        if parts.len() >= 4 && parts[0] == "root" {
            names.push(parts[2].to_string());
        }
    }
    names.sort();
    let mut output = String::from("{\n  \"packages\": [\n");
    for (idx, name) in names.iter().enumerate() {
        if idx > 0 {
            output.push_str(",\n");
        }
        output.push_str(&format!(
            "    {{\n      \"name\": \"{}\",\n      \"version\": \"0.0.0\",\n      \"features\": [],\n      \"dependencies\": []\n    }}",
            name
        ));
    }
    output.push_str("\n  ]\n}\n");
    if let Err(err) = fs::write(&opts.lock, output) {
        eprintln!("{err}");
        std::process::exit(1);
    }
    let _ = fs::write(&opts.report, "{\n  \"conflicts\": []\n}\n");
}

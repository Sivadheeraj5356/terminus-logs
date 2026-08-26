mod audit;
mod evaluate;
mod model;
mod publish;
mod report;
mod search;
mod types;
mod util;

use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process;

fn main() {
    let code = match run() {
        Ok(()) => 0,
        Err((code, diagnostic)) => {
            eprintln!("forest-audit: {diagnostic}");
            code
        }
    };
    process::exit(code);
}

fn run() -> Result<(), (i32, String)> {
    let args: Vec<String> = env::args().skip(1).collect();
    let (model_path, audit_path, output_path) = match args.as_slice() {
        [] => (
            PathBuf::from("/app/data/demo.forest"),
            PathBuf::from("/app/data/demo.audit"),
            PathBuf::from("/app/output/certificates.json"),
        ),
        [model, audit, output]
            if Path::new(model).is_absolute()
                && Path::new(audit).is_absolute()
                && Path::new(output).is_absolute() =>
        {
            (PathBuf::from(model), PathBuf::from(audit), PathBuf::from(output))
        }
        _ => return Err((64, "E_USAGE".to_string())),
    };

    let model_text = fs::read_to_string(&model_path).map_err(|_| (3, "E_IO".to_string()))?;
    let audit_text = fs::read_to_string(&audit_path).map_err(|_| (3, "E_IO".to_string()))?;
    let model = model::parse_model(&model_text).map_err(|error| (2, error.diagnostic()))?;
    let checks = audit::parse_audit(&audit_text, &model).map_err(|error| (2, error.diagnostic()))?;
    let model_hash = model::model_hash(&model);
    let results = search::run_checks(&model, checks);
    let bytes = report::render(&model_hash, &results);
    publish::publish(&output_path, &bytes).map_err(|_| (3, "E_PUBLISH".to_string()))?;
    Ok(())
}

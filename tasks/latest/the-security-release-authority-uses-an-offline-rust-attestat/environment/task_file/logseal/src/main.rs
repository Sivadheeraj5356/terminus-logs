use serde_json::json;
use std::env;
use std::fs;
use std::path::Path;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() != 3 {
        eprintln!("usage: logseal <input_dir> <output_dir>");
        std::process::exit(2);
    }
    let input_dir = Path::new(&args[1]);
    let output_dir = Path::new(&args[2]);
    fs::create_dir_all(output_dir).expect("create output dir");

    let policy_path = input_dir.join("policy.json");
    let generated_at = fs::read_to_string(policy_path)
        .ok()
        .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
        .and_then(|v| v.get("evaluation_time").and_then(|x| x.as_str()).map(str::to_string))
        .unwrap_or_default();

    let report = json!({
        "generated_at": generated_at,
        "artifacts": [],
        "summary": {"accepted": 0, "rejected": 0, "total": 0}
    });
    fs::write(
        output_dir.join("report.json"),
        serde_json::to_string_pretty(&report).expect("serialize report"),
    )
    .expect("write report");
}

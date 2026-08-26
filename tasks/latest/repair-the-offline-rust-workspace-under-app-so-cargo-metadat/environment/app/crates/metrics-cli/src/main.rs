use metrics_core::{summarize, MetricRecord, HEALTH_TOKEN};
use std::env;
use std::fs;
use std::path::PathBuf;

fn main() {
    let mut args = env::args().skip(1);
    let Some(flag) = args.next() else {
        eprintln!("usage: metrics-cli --health | --input PATH --out PATH");
        std::process::exit(2);
    };
    if flag == "--health" {
        println!("{HEALTH_TOKEN}");
        return;
    }
    if flag != "--input" {
        eprintln!("usage: metrics-cli --health | --input PATH --out PATH");
        std::process::exit(2);
    }
    let input = PathBuf::from(args.next().expect("input"));
    let out_flag = args.next().expect("out flag");
    if out_flag != "--out" {
        std::process::exit(2);
    }
    let out = PathBuf::from(args.next().expect("out"));
    let text = fs::read_to_string(input).expect("read input");
    let mut records = Vec::new();
    for line in text.lines() {
        if line.trim().is_empty() {
            continue;
        }
        records.push(serde_json::from_str::<MetricRecord>(line).expect("parse"));
    }
    let (total, services) = summarize(&records);
    let mut report = String::from("{\"recordCount\":");
    report.push_str(&serde_json::to_string(&records.len()).unwrap());
    report.push_str(",\"services\":");
    report.push_str(&serde_json::to_string(&services).unwrap());
    report.push_str(",\"totalLatencyMs\":");
    report.push_str(&serde_json::to_string(&total).unwrap());
    report.push_str("}\n");
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent).ok();
    }
    fs::write(out, report).unwrap();
}

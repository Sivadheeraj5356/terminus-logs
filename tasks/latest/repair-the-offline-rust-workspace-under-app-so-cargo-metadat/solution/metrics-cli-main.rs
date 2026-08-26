use metrics_core::{latency_bounds, service_totals, summarize, MetricRecord, HEALTH_TOKEN};
use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::Command;

fn sha256_file(path: &PathBuf) -> String {
    let output = Command::new("sha256sum")
        .arg(path)
        .output()
        .expect("sha256sum");
    String::from_utf8(output.stdout)
        .expect("utf8")
        .split_whitespace()
        .next()
        .expect("digest")
        .to_string()
}

fn policy_kind() -> String {
    let text = fs::read_to_string("/app/config/metadata-policy.json").expect("policy");
    let policy: serde_json::Value = serde_json::from_str(&text).expect("parse policy");
    policy["policyKind"].as_str().expect("policyKind").to_string()
}

fn write_service_totals(totals: &BTreeMap<String, u32>, out: &mut String) {
    out.push_str(",\"serviceTotals\":{");
    for (idx, (service, total)) in totals.iter().enumerate() {
        if idx > 0 {
            out.push(',');
        }
        out.push_str(&serde_json::to_string(service).unwrap());
        out.push(':');
        out.push_str(&total.to_string());
    }
    out.push('}');
}

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
    if policy_kind() != "metadata-release" {
        eprintln!("unexpected policy kind {}", policy_kind());
        std::process::exit(1);
    }
    let input = PathBuf::from(args.next().expect("input"));
    let out_flag = args.next().expect("out flag");
    if out_flag != "--out" {
        std::process::exit(2);
    }
    let out = PathBuf::from(args.next().expect("out"));
    let raw = fs::read(&input).expect("read input");
    let text = String::from_utf8(raw).expect("utf8 input");
    let mut records = Vec::new();
    for line in text.lines() {
        if line.trim().is_empty() {
            continue;
        }
        records.push(serde_json::from_str::<MetricRecord>(line).expect("parse"));
    }
    let (total, services) = summarize(&records);
    let totals = service_totals(&records);
    let (min_latency, max_latency) = latency_bounds(&records);
    let mut report = String::from("{\"services\":");
    report.push_str(&serde_json::to_string(&services).unwrap());
    write_service_totals(&totals, &mut report);
    report.push_str(",\"recordCount\":");
    report.push_str(&serde_json::to_string(&records.len()).unwrap());
    report.push_str(",\"totalLatencyMs\":");
    report.push_str(&serde_json::to_string(&total).unwrap());
    report.push_str("}\n");
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent).ok();
    }
    fs::write(&out, report).unwrap();

    let source_sha = sha256_file(&input);
    let mut summary = String::from("{\"policy_kind\":");
    summary.push_str(&serde_json::to_string(&policy_kind()).unwrap());
    summary.push_str(",\"record_count\":");
    summary.push_str(&serde_json::to_string(&records.len()).unwrap());
    summary.push_str(",\"unique_services\":");
    summary.push_str(&serde_json::to_string(&services.len()).unwrap());
    summary.push_str(",\"total_latency_ms\":");
    summary.push_str(&serde_json::to_string(&total).unwrap());
    summary.push_str(",\"max_latency_ms\":");
    summary.push_str(&serde_json::to_string(&max_latency).unwrap());
    summary.push_str(",\"min_latency_ms\":");
    summary.push_str(&serde_json::to_string(&min_latency).unwrap());
    summary.push_str(",\"source_sha256\":");
    summary.push_str(&serde_json::to_string(&source_sha).unwrap());
    summary.push_str("}\n");
    let summary_path = out.parent().expect("parent").join("metrics-summary.json");
    fs::write(summary_path, summary).unwrap();
}

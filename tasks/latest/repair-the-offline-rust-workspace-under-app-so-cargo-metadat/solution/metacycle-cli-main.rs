use metacycle_core::{build_audit_trail, build_metadata_manifest};
use std::env;
use std::fs;
use std::path::PathBuf;

fn main() {
    let mut args = env::args().skip(1);
    let cmd = args.next().unwrap_or_default();
    match cmd.as_str() {
        "graph" => run_graph(&mut args),
        "audit" => run_audit(&mut args),
        _ => {
            eprintln!("usage: metacycle graph|audit ...");
            std::process::exit(2);
        }
    }
}

fn run_graph(args: &mut impl Iterator<Item = String>) {
    let mut root = PathBuf::from("/app");
    let mut lock = PathBuf::from("config/graph-lock.csv");
    let mut out = PathBuf::from("output/dep-graph.json");
    while let Some(flag) = args.next() {
        match flag.as_str() {
            "--root" => root = PathBuf::from(args.next().unwrap()),
            "--lock" => lock = PathBuf::from(args.next().unwrap()),
            "--out" => out = PathBuf::from(args.next().unwrap()),
            _ => {}
        }
    }
    let json = metacycle_core::build_dep_graph(&root, &lock).unwrap();
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent).ok();
    }
    fs::write(out, json).unwrap();
}

fn run_audit(args: &mut impl Iterator<Item = String>) {
    let mut root = PathBuf::from("/app");
    let mut lock = PathBuf::from("config/graph-lock.csv");
    let mut policy_path = PathBuf::from("config/metadata-policy.json");
    let mut order_path = PathBuf::from("config/graph-order.csv");
    let mut out = PathBuf::from("dist/metadata-manifest.json");
    while let Some(flag) = args.next() {
        match flag.as_str() {
            "--root" => root = PathBuf::from(args.next().unwrap()),
            "--lock" => lock = PathBuf::from(args.next().unwrap()),
            "--policy" => policy_path = PathBuf::from(args.next().unwrap()),
            "--order" => order_path = PathBuf::from(args.next().unwrap()),
            "--out" => out = PathBuf::from(args.next().unwrap()),
            _ => {}
        }
    }
    let policy: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(&policy_path).unwrap()).unwrap();
    let rows = metacycle_core::read_lock(&lock).unwrap();
    let json = build_metadata_manifest(&rows, &root, &policy, &lock, &order_path).unwrap();
    fs::create_dir_all(out.parent().unwrap()).ok();
    fs::write(&out, json).unwrap();
    let trail = build_audit_trail(&rows, &root).unwrap();
    let trail_path = out.parent().unwrap().join("audit-trail.ndjson");
    fs::write(trail_path, trail).unwrap();
}

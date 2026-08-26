use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashMap};
use std::env;
use std::fs;
use std::process::exit;

#[derive(Debug, Deserialize)]
struct Assignment {
    lot_id: String,
    pallet_id: String,
    temp_band: String,
}

#[derive(Debug, Deserialize)]
struct Request {
    assignments: Vec<Assignment>,
}

#[derive(Debug, Serialize)]
struct Response {
    pallets: BTreeMap<String, Vec<String>>,
}

fn merge_k(req: Request) -> BTreeMap<String, Vec<String>> {
    let mut pallets: BTreeMap<String, Vec<String>> = BTreeMap::new();
    let mut band: HashMap<String, String> = HashMap::new();
    for row in req.assignments {
        let mut key = row.pallet_id.clone();
        if let Some(prev) = band.get(&key) {
            if prev != &row.temp_band {
                key = format!("{}-{}", row.pallet_id, row.temp_band);
            }
        }
        band.insert(key.clone(), row.temp_band.clone());
        pallets.entry(key).or_default().push(row.lot_id);
    }
    pallets
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut in_path = String::new();
    let mut out_path = String::new();
    let mut i = 1;
    while i < args.len() {
        if args[i] == "--in" && i + 1 < args.len() {
            in_path = args[i + 1].clone();
            i += 2;
            continue;
        }
        if args[i] == "--out" && i + 1 < args.len() {
            out_path = args[i + 1].clone();
            i += 2;
            continue;
        }
        i += 1;
    }
    if in_path.is_empty() || out_path.is_empty() {
        eprintln!("usage: pkmerge --in PATH --out PATH");
        exit(2);
    }
    let raw = fs::read_to_string(&in_path).unwrap_or_default();
    let req: Request = serde_json::from_str(&raw).unwrap_or(Request {
        assignments: vec![],
    });
    let resp = Response {
        pallets: merge_k(req),
    };
    let body = serde_json::to_vec_pretty(&resp).unwrap_or_default();
    let _ = fs::write(&out_path, body);
}

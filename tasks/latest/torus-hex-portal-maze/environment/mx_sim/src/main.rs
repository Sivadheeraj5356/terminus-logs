use std::env;
use std::fs;

use mx_core::{MapSpec, run_script};
use serde_json;

fn main() {
    let map_path = env::args().nth(1).expect("map json path required");
    let raw = fs::read_to_string(map_path).expect("read map");
    let spec: MapSpec = serde_json::from_str(&raw).expect("parse map");
    let outcome = run_script(&spec);
    let out = serde_json::to_string(&outcome).expect("serialize outcome");
    println!("{out}");
}

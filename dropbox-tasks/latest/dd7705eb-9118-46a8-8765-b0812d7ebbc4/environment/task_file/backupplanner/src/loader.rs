use crate::types::{Config, Job};
use std::fs;
use std::path::Path;

pub fn load_jobs(path: &Path) -> Vec<Job> {
    let data = fs::read_to_string(path).expect("read jobs.jsonl");
    data.lines()
        .filter(|line| !line.trim().is_empty())
        .map(|line| serde_json::from_str(line).expect("parse job"))
        .collect()
}

pub fn load_config(path: &Path) -> Config {
    serde_json::from_str(&fs::read_to_string(path).expect("read config.json")).expect("parse config")
}

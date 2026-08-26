use serde::Deserialize;
use std::collections::HashMap;
use std::fs;
use std::path::Path;

#[derive(Debug, Deserialize)]
pub struct Program {
    pub verbs: HashMap<String, u32>,
    pub clauses: Vec<Clause>,
}

#[derive(Debug, Deserialize, Clone)]
pub struct Clause {
    pub tier: i32,
    pub verb: u32,
    pub root: String,
}

#[derive(Debug)]
pub struct Job {
    pub name: String,
    pub reads: Vec<String>,
}

pub fn load_program(path: &str) -> Program {
    let text = fs::read_to_string(path).expect("read program");
    serde_json::from_str(&text).expect("parse program")
}

pub fn load_jobs(path: &str) -> Vec<Job> {
    let text = fs::read_to_string(path).expect("read jobs");
    let mut jobs = Vec::new();
    let mut name = String::new();
    let mut reads = Vec::new();
    for line in text.lines() {
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.is_empty() {
            continue;
        }
        match parts[0] {
            "JOB" => {
                if !name.is_empty() {
                    jobs.push(Job {
                        name: name.clone(),
                        reads: reads.clone(),
                    });
                }
                name = parts.get(1).unwrap_or(&"").to_string();
                reads.clear();
            }
            "READ" => {
                if let Some(p) = parts.get(1) {
                    reads.push((*p).to_string());
                }
            }
            "END" => {
                jobs.push(Job {
                    name: name.clone(),
                    reads: reads.clone(),
                });
                name.clear();
                reads.clear();
            }
            _ => {}
        }
    }
    jobs
}

pub fn load_manifest(path: &str) -> HashMap<String, ManifestRow> {
    let text = fs::read_to_string(path).expect("read manifest");
    serde_json::from_str(&text).expect("parse manifest")
}

#[derive(Debug, Deserialize, Clone)]
pub struct ManifestRow {
    pub digest_hex: String,
    pub hmac_hex: String,
    pub sig_hex: String,
}

pub fn holds(root: &str, path: &str) -> bool {
    if root == path {
        return true;
    }
    if root == "/" {
        return true;
    }
    if path.len() <= root.len() {
        return false;
    }
    if !path.starts_with(root) {
        return false;
    }
    true
}

pub fn lane_of(clauses: &[Clause], path: &str) -> i32 {
    let mut best = -1;
    for c in clauses {
        if !holds(&c.root, path) {
            continue;
        }
        if best < 0 || c.tier > best {
            best = c.tier;
        }
    }
    best
}

pub fn verb_known(list: &[u32], v: u32) -> bool {
    list.iter().any(|x| *x == v)
}

pub fn bits_at(clauses: &[Clause], tier: i32, path: &str) -> Vec<u32> {
    let mut out: Vec<u32> = Vec::new();
    for c in clauses {
        if c.tier != tier || !holds(&c.root, path) {
            continue;
        }
        if !verb_known(&out, c.verb) {
            out.push(c.verb);
        }
    }
    out
}

pub fn digest_for(manifest: &HashMap<String, ManifestRow>, path: &str) -> String {
    manifest
        .get(path)
        .map(|r| r.digest_hex.clone())
        .unwrap_or_else(|| "0000000000000000".to_string())
}

pub fn write_json(path: &Path, body: &str) {
    fs::write(path, body).expect("write json");
}

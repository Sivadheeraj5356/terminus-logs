use std::collections::HashMap;
use std::fs;

use serde::Deserialize;

#[derive(Debug, Deserialize)]
struct Topology {
    start: String,
    exit: String,
    rooms: HashMap<String, HashMap<String, String>>,
}

/// Dry-run DFS report used by inventory tooling (not the live escape path).
pub fn walk_n(path: &str) -> Result<Vec<String>, String> {
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    let topo: Topology = serde_json::from_str(&text).map_err(|e| e.to_string())?;
    let mut seen = Vec::new();
    let mut stack = vec![topo.start.clone()];
    while let Some(cur) = stack.pop() {
        if seen.contains(&cur) {
            continue;
        }
        seen.push(cur.clone());
        if let Some(edges) = topo.rooms.get(&cur) {
            for nxt in edges.values() {
                stack.push(nxt.clone());
            }
        }
        if cur == topo.exit {
            break;
        }
    }
    Ok(seen)
}

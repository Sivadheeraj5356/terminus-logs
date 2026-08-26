mod version;

use std::collections::HashMap;
use std::fs;
use std::path::Path;
use std::process::Command;

pub use version::{normalize_version, versions_match};

pub fn read_lock(path: &Path) -> Result<Vec<(String, String, String, String)>, String> {
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    let mut rows = Vec::new();
    for (idx, line) in text.lines().enumerate() {
        if idx == 0 || line.trim().is_empty() {
            continue;
        }
        let parts: Vec<&str> = line.split(',').collect();
        if parts.len() != 4 {
            return Err(format!("bad row {idx}"));
        }
        rows.push((parts[1].to_string(), parts[2].to_string(), parts[0].to_string(), parts[3].to_string()));
    }
    rows.sort_by(|a, b| b.0.cmp(&a.0));
    Ok(rows)
}

pub fn parse_cargo_lock(root: &Path) -> Result<HashMap<String, String>, String> {
    let text = fs::read_to_string(root.join("Cargo.lock")).map_err(|e| e.to_string())?;
    let mut versions = HashMap::new();
    let mut current: Option<String> = None;
    for line in text.lines() {
        let line = line.trim();
        if line == "[[package]]" {
            current = None;
            continue;
        }
        if let Some(rest) = line.strip_prefix("name = ") {
            current = Some(rest.trim_matches('"').to_string());
        }
        if let Some(rest) = line.strip_prefix("version = ") {
            if let Some(name) = current.clone() {
                versions.insert(name, rest.trim_matches('"').to_string());
            }
        }
    }
    Ok(versions)
}

pub fn build_dep_graph(root: &Path) -> Result<String, String> {
    let output = Command::new("cargo")
        .args(["metadata", "--format-version", "1", "--offline"])
        .current_dir(root)
        .output()
        .map_err(|e| e.to_string())?;
    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }
    let meta: serde_json::Value =
        serde_json::from_slice(&output.stdout).map_err(|e| e.to_string())?;
    let mut nodes = Vec::new();
    if let Some(pkgs) = meta["packages"].as_array() {
        for pkg in pkgs {
            let id = pkg["name"].as_str().unwrap_or("").to_string();
            let version = pkg["version"].as_str().unwrap_or("").to_string();
            if id.is_empty() {
                continue;
            }
            nodes.push(serde_json::json!({"id": id, "version": version}));
        }
    }
    nodes.sort_by(|a, b| {
        a["id"]
            .as_str()
            .unwrap_or("")
            .cmp(b["id"].as_str().unwrap_or(""))
    });
    let edge_count = meta["resolve"]["nodes"]
        .as_array()
        .map(|n| {
            n.iter()
                .map(|node| node["dependencies"].as_array().map(|d| d.len()).unwrap_or(0))
                .sum::<usize>()
        })
        .unwrap_or(0);
    let body = serde_json::json!({
        "edgeCount": edge_count,
        "nodes": nodes,
    });
    Ok(format!("{body}\n"))
}

pub fn build_metadata_manifest(
    rows: &[(String, String, String, String)],
    root: &Path,
    policy: &serde_json::Value,
) -> Result<String, String> {
    let lock = parse_cargo_lock(root)?;
    let mut deps = Vec::new();
    for (dep, want, role, kind) in rows {
        let got = lock.get(dep).ok_or_else(|| format!("missing lock entry for {dep}"))?;
        if !versions_match(want, got) {
            return Err(format!("version mismatch for {dep}"));
        }
        deps.push(serde_json::json!({
            "dep": dep,
            "version": got,
            "role": role,
            "kind": kind,
        }));
    }
    let body = serde_json::json!({
        "dependencies": deps,
        "metadataEpoch": policy["sourceDateEpoch"],
        "toolVersion": policy["toolVersion"],
        "vendorRoot": policy["vendorRoot"],
        "metadataPolicy": {
            "offlineLocked": false,
            "vendorRoot": policy["vendorRoot"],
        },
    });
    Ok(body.to_string())
}

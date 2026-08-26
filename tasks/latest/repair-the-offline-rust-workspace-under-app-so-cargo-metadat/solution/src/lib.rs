mod version;

use std::collections::{HashMap, HashSet};
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
        rows.push((
            parts[1].to_string(),
            parts[2].to_string(),
            parts[0].to_string(),
            parts[3].to_string(),
        ));
    }
    rows.sort_by(|a, b| a.0.cmp(&b.0));
    Ok(rows)
}

pub fn read_graph_order(path: &Path) -> Result<Vec<String>, String> {
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    let mut rows = Vec::new();
    for (idx, line) in text.lines().enumerate() {
        if idx == 0 || line.trim().is_empty() {
            continue;
        }
        let parts: Vec<&str> = line.split(',').collect();
        if parts.len() != 2 {
            return Err(format!("bad graph order row {idx}"));
        }
        let order: i32 = parts[0]
            .parse()
            .map_err(|_| format!("bad order at row {idx}"))?;
        rows.push((order, parts[1].to_string()));
    }
    rows.sort_by_key(|(order, _)| *order);
    Ok(rows.into_iter().map(|(_, dep)| dep).collect())
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

fn sha256_hex(bytes: &[u8]) -> String {
    use std::io::Write;
    use std::process::{Command, Stdio};
    let mut child = Command::new("sha256sum")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("spawn sha256sum");
    child
        .stdin
        .as_mut()
        .expect("stdin")
        .write_all(bytes)
        .expect("write stdin");
    let output = child.wait_with_output().expect("sha256sum output");
    String::from_utf8(output.stdout)
        .expect("utf8 stdout")
        .split_whitespace()
        .next()
        .expect("digest")
        .to_string()
}

fn module_graph_hash(deps: &[(String, String, String, String)]) -> String {
    let mut lines: Vec<String> = deps
        .iter()
        .map(|(dep, version, _, _)| format!("{dep}|{version}"))
        .collect();
    lines.sort();
    sha256_hex(lines.join("\n").as_bytes())
}

fn lock_digest(lock_path: &Path) -> Result<String, String> {
    Ok(sha256_hex(&fs::read(lock_path).map_err(|e| e.to_string())?))
}

fn package_name_map(meta: &serde_json::Value) -> HashMap<String, String> {
    let mut map = HashMap::new();
    if let Some(pkgs) = meta["packages"].as_array() {
        for pkg in pkgs {
            if let (Some(id), Some(name)) = (pkg["id"].as_str(), pkg["name"].as_str()) {
                map.insert(id.to_string(), name.to_string());
            }
        }
    }
    map
}

pub fn build_dep_graph(root: &Path, lock_path: &Path) -> Result<String, String> {
    let rows = read_lock(lock_path)?;
    let allowed: HashSet<String> = rows.iter().map(|(dep, _, _, _)| dep.clone()).collect();
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
    let mut versions = HashMap::new();
    if let Some(pkgs) = meta["packages"].as_array() {
        for pkg in pkgs {
            let id = pkg["name"].as_str().unwrap_or("").to_string();
            let version = pkg["version"].as_str().unwrap_or("").to_string();
            if allowed.contains(&id) {
                versions.insert(id, version);
            }
        }
    }
    let mut nodes = Vec::new();
    for (dep, _, _, _) in &rows {
        let version = versions
            .get(dep)
            .ok_or_else(|| format!("missing metadata version for {dep}"))?;
        nodes.push(serde_json::json!({"id": dep, "version": version}));
    }
    let id_names = package_name_map(&meta);
    let mut edge_count = 0usize;
    if let Some(resolve_nodes) = meta["resolve"]["nodes"].as_array() {
        for node in resolve_nodes {
            let node_id = node["id"].as_str().unwrap_or("");
            let node_name = id_names.get(node_id).cloned().unwrap_or_default();
            if !allowed.contains(&node_name) {
                continue;
            }
            if let Some(deps) = node["dependencies"].as_array() {
                for dep in deps {
                    let dep_id = dep.as_str().unwrap_or("");
                    let dep_name = id_names.get(dep_id).cloned().unwrap_or_default();
                    if allowed.contains(&dep_name) {
                        edge_count += 1;
                    }
                }
            }
        }
    }
    let mut out = String::new();
    out.push_str("{\"edgeCount\":");
    out.push_str(&edge_count.to_string());
    out.push_str(",\"nodes\":[");
    for (idx, node) in nodes.iter().enumerate() {
        if idx > 0 {
            out.push(',');
        }
        out.push_str("{\"id\":");
        out.push_str(&serde_json::to_string(&node["id"]).unwrap());
        out.push_str(",\"version\":");
        out.push_str(&serde_json::to_string(&node["version"]).unwrap());
        out.push_str("}");
    }
    out.push_str("]}");
    out.push('\n');
    Ok(out)
}

pub fn build_metadata_manifest(
    rows: &[(String, String, String, String)],
    root: &Path,
    policy: &serde_json::Value,
    lock_path: &Path,
    order_path: &Path,
) -> Result<String, String> {
    let lock = parse_cargo_lock(root)?;
    let graph_order = read_graph_order(order_path)?;
    let mut deps = Vec::new();
    for (dep, want, role, kind) in rows {
        let got = lock.get(dep).ok_or_else(|| format!("missing lock entry for {dep}"))?;
        if !versions_match(want, got) {
            return Err(format!("version mismatch for {dep}"));
        }
        deps.push((dep.clone(), got.clone(), role.clone(), kind.clone()));
    }
    let digest = lock_digest(lock_path)?;
    let graph_hash = module_graph_hash(&deps);
    let mut out = String::new();
    out.push_str("{\"metadataEpoch\":");
    out.push_str(&serde_json::to_string(&policy["sourceDateEpoch"]).unwrap());
    out.push_str(",\"toolVersion\":");
    out.push_str(&serde_json::to_string(&policy["toolVersion"]).unwrap());
    out.push_str(",\"vendorRoot\":");
    out.push_str(&serde_json::to_string(&policy["vendorRoot"]).unwrap());
    out.push_str(",\"metadataPolicy\":{");
    out.push_str("\"offlineLocked\":true,");
    out.push_str("\"vendorRoot\":");
    out.push_str(&serde_json::to_string(&policy["vendorRoot"]).unwrap());
    out.push_str("},\"lockDigest\":");
    out.push_str(&serde_json::to_string(&digest).unwrap());
    out.push_str(",\"moduleGraphHash\":");
    out.push_str(&serde_json::to_string(&graph_hash).unwrap());
    out.push_str(",\"graphOrder\":");
    out.push_str(&serde_json::to_string(&graph_order).unwrap());
    out.push_str(",\"dependencies\":[");
    for (i, (dep, ver, role, kind)) in deps.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push_str("{\"dep\":");
        out.push_str(&serde_json::to_string(dep).unwrap());
        out.push_str(",\"version\":");
        out.push_str(&serde_json::to_string(ver).unwrap());
        out.push_str(",\"role\":");
        out.push_str(&serde_json::to_string(role).unwrap());
        out.push_str(",\"kind\":");
        out.push_str(&serde_json::to_string(kind).unwrap());
        out.push_str("}");
    }
    out.push_str("]}");
    out.push('\n');
    Ok(out)
}

pub fn build_audit_trail(
    rows: &[(String, String, String, String)],
    root: &Path,
) -> Result<String, String> {
    let lock = parse_cargo_lock(root)?;
    let mut lines = Vec::new();
    for (dep, want, role, kind) in rows {
        let got = lock.get(dep).ok_or_else(|| format!("missing lock entry for {dep}"))?;
        let matched = versions_match(want, got);
        let mut line = String::new();
        line.push_str("{\"dep\":");
        line.push_str(&serde_json::to_string(dep).unwrap());
        line.push_str(",\"kind\":");
        line.push_str(&serde_json::to_string(kind).unwrap());
        line.push_str(",\"matched\":");
        line.push_str(if matched { "true" } else { "false" });
        line.push_str(",\"role\":");
        line.push_str(&serde_json::to_string(role).unwrap());
        line.push_str(",\"version\":");
        line.push_str(&serde_json::to_string(got).unwrap());
        line.push_str("}");
        lines.push(line);
    }
    Ok(format!("{}\n", lines.join("\n")))
}

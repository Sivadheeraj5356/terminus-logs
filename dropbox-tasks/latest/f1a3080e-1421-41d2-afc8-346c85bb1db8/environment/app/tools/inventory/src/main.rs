//! Emit the dependency inventory for the native runtime closure.
//!
//! The closure is derived by walking the native library's path dependencies,
//! so it reflects the crates actually compiled into libvellum, not a static
//! list. Usage: inventory --root <dir>

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::exit;

use docmodel::{dump_compact, sha256_hex, Value};

fn arg_value(args: &[String], flag: &str) -> Option<String> {
    args.iter()
        .position(|a| a == flag)
        .and_then(|i| args.get(i + 1))
        .cloned()
}

#[derive(Clone)]
struct Component {
    ecosystem: String,
    name: String,
    version: String,
    source: String,
    checksum: String,
}

fn manifest_field(text: &str, key: &str) -> Option<String> {
    for line in text.lines() {
        let line = line.trim();
        if let Some(rest) = line.strip_prefix(key) {
            let rest = rest.trim_start();
            if let Some(v) = rest.strip_prefix('=') {
                return Some(v.trim().trim_matches('"').to_string());
            }
        }
    }
    None
}

/// Collect `name = { path = "..." }` dependency entries from a manifest body.
fn manifest_path_deps(text: &str) -> Vec<(String, String)> {
    let mut deps = Vec::new();
    let mut in_deps = false;
    for line in text.lines() {
        let trimmed = line.trim();
        if trimmed.starts_with('[') {
            in_deps = trimmed == "[dependencies]";
            continue;
        }
        if !in_deps || trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }
        if let Some((name, rhs)) = trimmed.split_once('=') {
            if let Some(start) = rhs.find("path") {
                let after = &rhs[start..];
                if let Some(q1) = after.find('"') {
                    if let Some(q2) = after[q1 + 1..].find('"') {
                        let path = &after[q1 + 1..q1 + 1 + q2];
                        deps.push((name.trim().to_string(), path.to_string()));
                    }
                }
            }
        }
    }
    deps
}

fn tree_sha(dir: &Path) -> String {
    let mut files: Vec<PathBuf> = Vec::new();
    collect_files(dir, &mut files);
    files.sort();
    let mut acc: Vec<u8> = Vec::new();
    for file in &files {
        let rel = file.strip_prefix(dir).unwrap().to_string_lossy();
        acc.extend_from_slice(rel.as_bytes());
        acc.push(0);
        if let Ok(bytes) = fs::read(file) {
            acc.extend_from_slice(&bytes);
        }
        acc.push(0);
    }
    sha256_hex(&acc)
}

fn collect_files(dir: &Path, out: &mut Vec<PathBuf>) {
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let name = entry.file_name();
        if name == "target" {
            continue;
        }
        if path.is_dir() {
            collect_files(&path, out);
        } else {
            out.push(path);
        }
    }
}

fn walk(dir: &Path, acc: &mut BTreeMap<String, Component>) {
    let manifest_path = dir.join("Cargo.toml");
    let Ok(text) = fs::read_to_string(&manifest_path) else {
        return;
    };
    let name = manifest_field(&text, "name").unwrap_or_default();
    let version = manifest_field(&text, "version").unwrap_or_default();
    if name.is_empty() || acc.contains_key(&name) {
        // already recorded (or unreadable); still descend once via the guard below
    }
    if !acc.contains_key(&name) && !name.is_empty() {
        let is_vendored = dir
            .components()
            .any(|c| c.as_os_str() == "vendor");
        acc.insert(
            name.clone(),
            Component {
                ecosystem: "cargo".to_string(),
                name: name.clone(),
                version,
                source: if is_vendored { "vendored" } else { "workspace" }.to_string(),
                checksum: format!("sha256:{}", tree_sha(dir)),
            },
        );
        for (_dep, rel) in manifest_path_deps(&text) {
            let dep_dir = normalize(&dir.join(rel));
            walk(&dep_dir, acc);
        }
    }
}

fn normalize(path: &Path) -> PathBuf {
    let mut parts: Vec<std::ffi::OsString> = Vec::new();
    for comp in path.components() {
        use std::path::Component::*;
        match comp {
            ParentDir => {
                parts.pop();
            }
            CurDir => {}
            other => parts.push(other.as_os_str().to_os_string()),
        }
    }
    let mut result = PathBuf::new();
    for part in parts {
        result.push(part);
    }
    result
}

fn toolchain_component(root: &Path) -> Component {
    let text = fs::read_to_string(root.join("rust-toolchain.toml")).unwrap_or_default();
    let channel = manifest_field(&text, "channel").unwrap_or_else(|| "unknown".to_string());
    Component {
        ecosystem: "native".to_string(),
        name: "rustc".to_string(),
        version: channel.clone(),
        source: "toolchain".to_string(),
        checksum: format!("sha256:{}", sha256_hex(channel.as_bytes())),
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let root = PathBuf::from(arg_value(&args, "--root").unwrap_or_else(|| ".".to_string()));

    let mut acc: BTreeMap<String, Component> = BTreeMap::new();
    walk(&root.join("crates").join("bridge"), &mut acc);
    let toolchain = toolchain_component(&root);

    let mut components: Vec<Component> = acc.into_values().collect();
    components.push(toolchain);
    components.sort_by(|a, b| {
        (a.ecosystem.as_str(), a.name.as_str(), a.version.as_str(), a.checksum.as_str()).cmp(&(
            b.ecosystem.as_str(),
            b.name.as_str(),
            b.version.as_str(),
            b.checksum.as_str(),
        ))
    });

    if components.iter().all(|c| c.name != "bridge") {
        eprintln!("inventory: could not resolve native closure");
        exit(1);
    }

    let component_values: Vec<Value> = components
        .iter()
        .map(|c| {
            Value::Obj(vec![
                ("checksum".to_string(), Value::Str(c.checksum.clone())),
                ("ecosystem".to_string(), Value::Str(c.ecosystem.clone())),
                ("name".to_string(), Value::Str(c.name.clone())),
                ("source".to_string(), Value::Str(c.source.clone())),
                ("version".to_string(), Value::Str(c.version.clone())),
            ])
        })
        .collect();
    let components_arr = Value::Arr(component_values);
    let closure_digest = format!("sha256:{}", sha256_hex(dump_compact(&components_arr).as_bytes()));

    let root_value = Value::Obj(vec![
        ("closure_digest".to_string(), Value::Str(closure_digest)),
        ("components".to_string(), components_arr),
        ("schema_version".to_string(), Value::Int(1)),
    ]);
    println!("{}", dump_compact(&root_value));
}

//! Resolve a single release plan from the profile and identity inputs.

use std::env;
use std::fs;
use std::path::Path;

use crate::conf::Profile;
use docmodel::Value;

#[derive(Debug, Clone)]
pub struct Plan {
    pub version: String,
    pub revision: String,
    pub epoch: i64,
    pub target: String,
    pub capabilities: Vec<String>,
}

fn read_trimmed(path: &Path) -> String {
    fs::read_to_string(path)
        .map(|s| s.trim().to_string())
        .unwrap_or_default()
}

pub fn resolve(root: &Path) -> Plan {
    let version = read_trimmed(&root.join("VERSION"));
    let revision = read_trimmed(&root.join("REVISION"));
    let profile_text = fs::read_to_string(root.join("config").join("release.toml"))
        .unwrap_or_default();
    let profile = Profile::parse(&profile_text);

    let epoch = profile.int("epoch").unwrap_or(0);
    let target = profile
        .string("target")
        .unwrap_or("x86_64-unknown-linux-gnu")
        .to_string();

    let mut capabilities = profile.list("capabilities");
    apply_local_overrides(&mut capabilities);
    normalize(&mut capabilities);

    Plan {
        version,
        revision,
        epoch,
        target,
        capabilities,
    }
}

fn apply_local_overrides(names: &mut Vec<String>) {
    if let Ok(extra) = env::var("VELLUM_DEV_CAPS") {
        for name in extra.split(',') {
            let name = name.trim();
            if !name.is_empty() {
                names.push(name.to_string());
            }
        }
    }
}

fn normalize(names: &mut Vec<String>) {
    if !names.iter().any(|n| n == "core") {
        names.push("core".to_string());
    }
    names.sort();
    names.dedup();
}

impl Plan {
    /// Non-core capabilities become cargo feature flags.
    pub fn features(&self) -> Vec<String> {
        self.capabilities
            .iter()
            .filter(|c| c.as_str() != "core")
            .cloned()
            .collect()
    }

    pub fn to_json(&self) -> String {
        let caps: Vec<Value> = self
            .capabilities
            .iter()
            .cloned()
            .map(Value::Str)
            .collect();
        let root = Value::Obj(vec![
            ("capabilities".to_string(), Value::Arr(caps)),
            ("epoch".to_string(), Value::Int(self.epoch)),
            ("revision".to_string(), Value::Str(self.revision.clone())),
            ("target".to_string(), Value::Str(self.target.clone())),
            ("version".to_string(), Value::Str(self.version.clone())),
        ]);
        docmodel::dump_compact(&root)
    }
}

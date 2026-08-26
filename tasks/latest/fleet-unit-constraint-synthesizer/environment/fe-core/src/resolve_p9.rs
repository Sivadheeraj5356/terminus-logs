use serde_json::Value;
use std::collections::BTreeMap;

use crate::layer_r4;

pub type Doc = BTreeMap<String, Value>;

pub fn pick_scalar(layers: &[(&str, Option<&str>)]) -> Option<String> {
    let mut best: Option<(&str, &str)> = None;
    for (layer, val) in layers {
        if let Some(v) = val {
            match best {
                None => best = Some((layer, v)),
                Some((bl, _)) if layer_r4::beats(layer, bl) => best = Some((layer, v)),
                _ => {}
            }
        }
    }
    best.map(|(_, v)| v.to_string())
}

pub fn pick_list(layers: &[(&str, Option<&Vec<String>>)]) -> Vec<String> {
    // BUG: unions every defined layer instead of replacing with the highest layer.
    let mut merged: Vec<String> = Vec::new();
    for (_, val) in layers {
        if let Some(v) = val {
            for item in v.iter() {
                if !merged.contains(item) {
                    merged.push(item.clone());
                }
            }
        }
    }
    merged
}

pub fn resolve_service(
    manifest: &Value,
    cli: &BTreeMap<String, String>,
    env: &BTreeMap<String, String>,
    name: &str,
) -> Doc {
    let svc = manifest["services"][name].clone();
    let m_restart = svc["restart"].as_str();
    let m_rsec = svc["restart_sec"].as_i64().map(|n| n.to_string());
    let m_slice = None::<String>;
    let m_after = svc["after"].as_array().map(|a| {
        a.iter()
            .filter_map(|v| v.as_str().map(str::to_string))
            .collect::<Vec<_>>()
    });
    let m_req = svc["requires"].as_array().map(|a| {
        a.iter()
            .filter_map(|v| v.as_str().map(str::to_string))
            .collect::<Vec<_>>()
    });
    let m_wants = svc["wants"].as_array().map(|a| {
        a.iter()
            .filter_map(|v| v.as_str().map(str::to_string))
            .collect::<Vec<_>>()
    });

    let prefix = name
        .trim_end_matches(".service")
        .replace('.', "_")
        .replace('-', "_")
        .to_uppercase();
    let cli_restart = cli.get(&format!("{prefix}_RESTART")).map(|s| s.as_str());
    let cli_rsec = cli.get(&format!("{prefix}_RESTART_SEC")).map(|s| s.as_str());
    let cli_slice = cli.get(&format!("{prefix}_SLICE")).map(|s| s.as_str());
    let cli_after = cli
        .get(&format!("{prefix}_AFTER"))
        .map(|s| s.split(',').map(str::trim).filter(|x| !x.is_empty()).map(str::to_string).collect());
    let cli_req = cli
        .get(&format!("{prefix}_REQUIRES"))
        .map(|s| s.split(',').map(str::trim).filter(|x| !x.is_empty()).map(str::to_string).collect());

    let env_restart = env.get(&format!("{prefix}_RESTART")).map(|s| s.as_str());
    let env_rsec = env.get(&format!("{prefix}_RESTART_SEC")).map(|s| s.as_str());
    let env_slice = env.get(&format!("{prefix}_SLICE")).map(|s| s.as_str());

    let restart = pick_scalar(&[
        ("cli", cli_restart),
        ("env", env_restart),
        ("manifest", m_restart),
        ("default", Some("on-failure")),
    ]);
    let restart_sec = pick_scalar(&[
        ("cli", cli_rsec),
        ("env", env_rsec),
        ("manifest", m_rsec.as_deref()),
        ("default", Some("30")),
    ]);
    let slice = pick_scalar(&[
        ("cli", cli_slice),
        ("env", env_slice),
        ("manifest", m_slice.as_deref()),
        ("default", None),
    ]);

    let after = pick_list(&[
        ("cli", cli_after.as_ref()),
        ("env", None),
        ("manifest", m_after.as_ref()),
        ("default", None),
    ]);
    let requires = pick_list(&[
        ("cli", cli_req.as_ref()),
        ("env", None),
        ("manifest", m_req.as_ref()),
        ("default", None),
    ]);
    let wants = pick_list(&[
        ("cli", None),
        ("env", None),
        ("manifest", m_wants.as_ref()),
        ("default", None),
    ]);

    let mut out = BTreeMap::new();
    out.insert("restart".into(), Value::String(restart.unwrap_or_else(|| "on-failure".into())));
    out.insert(
        "restart_sec".into(),
        Value::String(restart_sec.unwrap_or_else(|| "30".into())),
    );
    if let Some(sl) = slice {
        out.insert("slice".into(), Value::String(sl));
    }
    out.insert(
        "after".into(),
        Value::Array(after.into_iter().map(Value::String).collect()),
    );
    out.insert(
        "requires".into(),
        Value::Array(requires.into_iter().map(Value::String).collect()),
    );
    out.insert(
        "wants".into(),
        Value::Array(wants.into_iter().map(Value::String).collect()),
    );
    out
}

use std::fs;
use std::path::Path;

pub fn load_profile_mask(profile: &str) -> u32 {
    let path = Path::new("/app/environment/ops/overlays").join(format!("{profile}.json"));
    let raw = fs::read_to_string(path).unwrap_or_else(|_| "{}".into());
    let v: serde_json::Value = serde_json::from_str(&raw).unwrap_or(serde_json::json!({}));
    v["mask"].as_u64().unwrap_or(0xFFFF_FFFF) as u32
}

pub fn effective_mask(profile: &str, sweep_mask: u32) -> u32 {
    sweep_mask & load_profile_mask(profile)
}

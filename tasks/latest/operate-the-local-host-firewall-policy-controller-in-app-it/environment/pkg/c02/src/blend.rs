use std::path::Path;

use hx01::model::{DropInMeta, PolicyIntent};
use hx01::Result;

use crate::parse::load_dropin;
use crate::rank::sort_dropin_entries;

pub fn blend_dropins(base: PolicyIntent, dropin_dir: &Path) -> Result<(PolicyIntent, Vec<DropInMeta>)> {
    let mut intent = base;
    let mut sources = Vec::new();
    if !dropin_dir.is_dir() {
        return Ok((intent, sources));
    }
    let mut entries: Vec<(i32, String, PolicyIntent)> = Vec::new();
    for entry in std::fs::read_dir(dropin_dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.extension().and_then(|s| s.to_str()) == Some("toml") {
            let (dropin, priority, normalized) = load_dropin(&path)?;
            entries.push((priority, normalized.clone(), dropin));
            sources.push(DropInMeta {
                path: normalized,
                priority,
            });
        }
    }
    sort_dropin_entries(&mut entries);
    for (_, _, dropin) in entries {
        intent = overlay_intent(intent, dropin);
    }
    Ok((intent, sources))
}

pub fn overlay_intent(mut base: PolicyIntent, overlay: PolicyIntent) -> PolicyIntent {
    for (tenant, overlay_tenant) in overlay.tenants {
        let entry = base.tenants.entry(tenant).or_insert_with(|| hx01::model::TenantIntent {
            sets: Default::default(),
            chains: Default::default(),
            rules: Default::default(),
        });
        for (k, v) in overlay_tenant.sets {
            entry.sets.insert(k, v);
        }
        for (k, v) in overlay_tenant.rules {
            entry.rules.insert(k, v);
        }
        for (k, v) in overlay_tenant.chains {
            entry.chains.insert(k, v);
        }
    }
    base
}

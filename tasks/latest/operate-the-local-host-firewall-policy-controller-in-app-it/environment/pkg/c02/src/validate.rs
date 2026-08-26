use std::path::Path;

use hx01::model::{EffectiveConfig, PolicyIntent, RuntimeOverrides};
use hx01::{PolicyError, Result};

use crate::blend::blend_dropins;
use crate::adjunct::apply_runtime_adjuncts;
use crate::parse::load_base;
use crate::rank::sort_dropin_sources;

pub struct EffectiveBuild {
    pub intent: PolicyIntent,
    pub effective: EffectiveConfig,
}

pub fn build_effective(base_path: &Path, dropin_dir: &Path, overrides_path: &Path) -> Result<EffectiveBuild> {
    let (base, _) = load_base(base_path)?;
    let (mut intent, mut sources) = blend_dropins(base, dropin_dir)?;
    sort_dropin_sources(&mut sources);
    let overrides_text = std::fs::read_to_string(overrides_path).unwrap_or_else(|_| "{}".into());
    let overrides: RuntimeOverrides = serde_json::from_str(&overrides_text)?;
    intent = apply_runtime_adjuncts(intent, &overrides)?;
    let effective = EffectiveConfig {
        tenants: intent.tenants.clone(),
        sources,
    };
    Ok(EffectiveBuild { intent, effective })
}

pub fn validate_effective(build: &EffectiveBuild) -> Result<()> {
    for (tenant, t) in &build.intent.tenants {
        for (rule_id, rule) in &t.rules {
            if let Some(src) = &rule.src_set {
                if !t.sets.contains_key(&src.0) {
                    return Err(PolicyError::Validation(format!(
                        "tenant {tenant} rule {rule_id} references unknown set {}",
                        src.0
                    )));
                }
            }
            if let Some(dst) = &rule.dst_set {
                if !t.sets.contains_key(&dst.0) {
                    return Err(PolicyError::Validation(format!(
                        "tenant {tenant} rule {rule_id} references unknown set {}",
                        dst.0
                    )));
                }
            }
        }
        let mut seen = indexmap::IndexSet::new();
        if let Some(chain) = t.chains.get("ingress") {
            for rid in &chain.rules {
                if !seen.insert(rid.0.clone()) {
                    return Err(PolicyError::Validation(format!(
                        "duplicate rule {rid:?} in ordered chain for tenant {tenant}"
                    )));
                }
            }
        }
    }
    Ok(())
}

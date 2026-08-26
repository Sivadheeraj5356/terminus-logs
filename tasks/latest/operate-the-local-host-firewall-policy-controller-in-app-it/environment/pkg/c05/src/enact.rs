use std::path::Path;

use hx04::failpoints::{
    self, AFTER_MANIFEST_PUBLISH, AFTER_PUBLISH_REFERENCES, AFTER_STAGE_CHAINS, AFTER_STAGE_SETS,
};
use hx04::simulator::{simulate_with_sets, BackendStore};
use hx03::compile_intent;
use hx02::validate::{build_effective, validate_effective};
use hx01::model::{
    Annotation, BackendRule, BackendState, ManifestEntry, ManifestGeneration, OwnershipManifest,
    RuleAction, RuleSpec,
};
use hx01::status::StatusReport;
use hx01::{PolicyError, Result};

use crate::tally::transfer_counters;
use crate::roster::{audit_append, load_roster, save_roster};
use crate::tenure::annotation_from_entry;

pub struct StatePaths {
    pub base: std::path::PathBuf,
    pub dropins: std::path::PathBuf,
    pub overrides: std::path::PathBuf,
    pub backend: std::path::PathBuf,
    pub manifest: std::path::PathBuf,
    pub audit: std::path::PathBuf,
}

impl StatePaths {
    pub fn from_state_dir(state_dir: &Path) -> Self {
        let base = std::env::var("NX_CONFIG")
            .map(|p| Path::new(&p).to_path_buf())
            .unwrap_or_else(|_| Path::new("/app/config/base.toml").to_path_buf());
        let dropins = std::env::var("NX_DROPIN_DIR")
            .map(|p| Path::new(&p).to_path_buf())
            .unwrap_or_else(|_| Path::new("/app/config/conf.d").to_path_buf());
        Self {
            base,
            dropins,
            overrides: state_dir.join("runtime-overrides.json"),
            backend: state_dir.join("backend.json"),
            manifest: state_dir.join("ownership-manifest.json"),
            audit: state_dir.join("audit.jsonl"),
        }
    }
}

/// Apply the effective policy to durable controller state.
pub fn enact_ruleset(paths: &StatePaths) -> Result<StatusReport> {
    let build = build_effective(&paths.base, &paths.dropins, &paths.overrides)?;
    let mut backend = BackendStore::open(&paths.backend)?;
    let old_state = backend.state.clone();
    let mut manifest = load_roster(&paths.manifest)?;

    let compiled = compile_intent(&build.intent)?;
    stage_sets(&mut backend.state, &compiled, &mut manifest)?;
    failpoints::check_failpoint(AFTER_STAGE_SETS)?;

    if let Err(e) = validate_effective(&build) {
        return Err(e);
    }

    stage_chains(&mut backend.state, &compiled, &mut manifest)?;
    failpoints::check_failpoint(AFTER_STAGE_CHAINS)?;

    publish_rules(&mut backend.state, &build.intent, &compiled, manifest.committed.generation + 1)?;
    failpoints::check_failpoint(AFTER_PUBLISH_REFERENCES)?;

    transfer_counters(&old_state, &mut backend.state);

    manifest.committed = ManifestGeneration {
        generation: manifest.committed.generation + 1,
        phase: "committed".into(),
        entries: compiled
            .objects
            .iter()
            .map(|o| ManifestEntry {
                logical_id: o.logical_id.clone(),
                visible_name: o.visible_name.clone(),
                kind: o.kind,
                generation: manifest.committed.generation + 1,
                semantic_revision: o.semantic_revision.clone(),
                counter_lineage: Some(o.logical_id.0.clone()),
            })
            .collect(),
    };
    manifest.pending = None;
    save_roster(&paths.manifest, &manifest)?;
    failpoints::check_failpoint(AFTER_MANIFEST_PUBLISH)?;

    backend.save()?;
    audit_append(
        &paths.audit,
        &serde_json::json!({
            "operation": "apply",
            "phase": "committed",
            "outcome": "ok",
            "reason_code": null
        }),
    )?;
    Ok(status_from(&backend.state, &manifest))
}

fn stage_sets(
    state: &mut BackendState,
    compiled: &hx01::model::CompiledIntent,
    manifest: &mut OwnershipManifest,
) -> Result<()> {
    for obj in &compiled.objects {
        if matches!(obj.kind, hx01::ids::ObjectKind::Set) {
            if let Ok(set) = serde_json::from_value::<hx01::model::AddressSet>(obj.payload.clone()) {
                state.sets.insert(obj.visible_name.clone(), set.members.clone());
            }
        }
    }
    manifest.pending = Some(ManifestGeneration {
        generation: manifest.committed.generation + 1,
        phase: "after-stage-sets".into(),
        entries: compiled
            .objects
            .iter()
            .map(|o| ManifestEntry {
                logical_id: o.logical_id.clone(),
                visible_name: o.visible_name.clone(),
                kind: o.kind,
                generation: manifest.committed.generation + 1,
                semantic_revision: o.semantic_revision.clone(),
                counter_lineage: Some(o.logical_id.0.clone()),
            })
            .collect(),
    });
    Ok(())
}

fn stage_chains(
    state: &mut BackendState,
    compiled: &hx01::model::CompiledIntent,
    manifest: &mut OwnershipManifest,
) -> Result<()> {
    if let Some(pending) = manifest.pending.as_mut() {
        pending.phase = "after-stage-chains".into();
    }
    let _ = (state, compiled);
    Ok(())
}

fn publish_rules(
    state: &mut BackendState,
    intent: &hx01::model::PolicyIntent,
    compiled: &hx01::model::CompiledIntent,
    generation: u64,
) -> Result<()> {
    state.rules.clear();
    state.chains.clear();
    for (tenant_name, tenant) in &intent.tenants {
        let chain_name = format!("chain-{tenant_name}");
        let mut handles = Vec::new();
        if let Some(chain) = tenant.chains.get("ingress") {
            for rid in &chain.rules {
                if let Some(rule) = tenant.rules.get(&rid.0) {
                    let obj = compiled
                        .objects
                        .iter()
                        .find(|o| o.logical_id.0 == rid.0)
                        .ok_or_else(|| PolicyError::Reconcile(format!("missing compiled rule {}", rid.0)))?;
                    let handle = state.next_handle;
                    state.next_handle += 1;
                    let src = rule.src_set.as_ref().map(|s| {
                        compiled
                            .objects
                            .iter()
                            .find(|o| o.logical_id.0 == s.0)
                            .map(|o| o.visible_name.clone())
                            .unwrap_or_else(|| s.0.clone())
                    });
                    state.rules.insert(
                        handle,
                        BackendRule {
                            handle,
                            visible_name: obj.visible_name.clone(),
                            annotation: Some(Annotation {
                                managed: true,
                                logical_id: rule.id.clone(),
                                generation,
                                phase: "committed".into(),
                                tenant: tenant_name.clone(),
                                counter_lineage: Some(rule.id.0.clone()),
                            }),
                            action: rule.action.clone(),
                            src_set: src,
                            dst_set: rule.dst_set.as_ref().map(|s| s.0.clone()),
                            dst_port: rule.dst_port,
                            chain: chain_name.clone(),
                            counter: 0,
                        },
                    );
                    handles.push(handle);
                }
            }
        }
        state.chains.insert(chain_name, handles);
        for (set_id, set) in &tenant.sets {
            let visible = compiled
                .objects
                .iter()
                .find(|o| o.logical_id.0 == *set_id)
                .map(|o| o.visible_name.clone())
                .unwrap_or_else(|| set_id.clone());
            state.sets.insert(visible, set.members.clone());
        }
    }
    Ok(())
}

pub fn status_from(state: &BackendState, manifest: &OwnershipManifest) -> StatusReport {
    let managed = state.rules.values().filter(|r| r.annotation.as_ref().map(|a| a.managed).unwrap_or(false)).count();
    let foreign = state.rules.len() - managed;
    StatusReport {
        schema_version: 1,
        ok: true,
        phase: manifest.committed.phase.clone(),
        generation: manifest.committed.generation,
        pending_generation: manifest.pending.as_ref().map(|p| p.generation),
        managed_rules: managed,
        foreign_rules: foreign,
        reason_codes: vec![],
    }
}

pub fn simulate_packet(state: &BackendState, packet: &hx01::model::Packet) -> hx01::model::PacketResult {
    simulate_with_sets(state, packet)
}

pub fn rule_from_spec(rule: &RuleSpec, visible: &str, generation: u64, tenant: &str) -> BackendRule {
    BackendRule {
        handle: 0,
        visible_name: visible.into(),
        annotation: Some(Annotation {
            managed: true,
            logical_id: rule.id.clone(),
            generation,
            phase: "staged".into(),
            tenant: tenant.into(),
            counter_lineage: Some(rule.id.0.clone()),
        }),
        action: rule.action.clone(),
        src_set: rule.src_set.as_ref().map(|s| s.0.clone()),
        dst_set: rule.dst_set.as_ref().map(|s| s.0.clone()),
        dst_port: rule.dst_port,
        chain: "ingress".into(),
        counter: 0,
    }
}

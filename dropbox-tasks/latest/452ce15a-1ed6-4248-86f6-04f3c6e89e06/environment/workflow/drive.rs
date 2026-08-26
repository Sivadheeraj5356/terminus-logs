use std::path::Path;

use crate::calib::apply::{effective_nominal_header, ResolvedInputs};
use crate::calib::profile::profile_graph_hash;
use crate::folio::bind::merge_batch;
use crate::state::manifest::{
    commit_success, fingerprint_inputs, read_manifest, resolve_batch_generation,
    resolve_branch_generation,
};
use crate::types::BatchReport;
use crate::workflow::emit::{emit_batch_report, FamilyEmitInput};
use crate::workflow::process::rows_for_family;

pub fn audit_paths(paths: &[impl AsRef<Path>], as_of: &str) -> Result<BatchReport, String> {
    let input_fingerprint = fingerprint_inputs(paths, as_of)?;
    let merged = merge_batch(paths, as_of)?;
    let profile_graph_hash = profile_graph_hash(&merged.all_revisions, &merged.all_segment_overrides);

    let manifest_before = read_manifest();
    let batch_key_is_new = manifest_before.last_input_fingerprint != input_fingerprint
        || manifest_before.last_profile_graph_hash != profile_graph_hash;

    let batch_generation = resolve_batch_generation(&input_fingerprint, &profile_graph_hash);

    let mut family_inputs = Vec::new();
    let mut family_branches = Vec::new();

    let mut family_ids: Vec<String> = merged.families.keys().cloned().collect();
    family_ids.sort();

    for family_id in family_ids {
        let family = merged
            .families
            .get(&family_id)
            .ok_or_else(|| format!("missing family {family_id}"))?;
        let branch_generation = resolve_branch_generation(
            &family_id,
            &input_fingerprint,
            &profile_graph_hash,
            batch_generation,
            batch_key_is_new,
        );
        family_branches.push((family_id.clone(), branch_generation));

        let ctx = crate::workflow::process::CalibContext {
            profile: &family.profile,
            resolved: &family.resolved,
        };
        let rows = rows_for_family(
            &ctx,
            &input_fingerprint,
            &profile_graph_hash,
            &family_id,
        )?;
        let nominal_hz = effective_nominal_header(&family.profile, &family.resolved);

        family_inputs.push(FamilyEmitInput {
            family_id: family_id.clone(),
            chip_id: family.profile.chip_id.clone(),
            alias: family.profile.alias.clone(),
            profile_id: family.profile.profile_id.clone(),
            nominal_hz,
            branch_generation,
            rows,
            provenance: family.provenance.clone(),
            lineage: family.lineage_revisions.clone(),
        });
    }

    let report = emit_batch_report(
        as_of.to_string(),
        input_fingerprint.clone(),
        profile_graph_hash.clone(),
        batch_generation,
        family_inputs,
    );

    commit_success(
        &input_fingerprint,
        &profile_graph_hash,
        batch_generation,
        &family_branches,
        batch_key_is_new,
    )?;

    Ok(report)
}

use crate::seal::mark::{batch_seal, resonance_seal};
use crate::types::{BatchReport, FamilyReport, REPORT_SCHEMA_VERSION};
use crate::workflow::summarize::summarize_pull;

pub struct FamilyEmitInput {
    pub family_id: String,
    pub chip_id: String,
    pub alias: String,
    pub profile_id: String,
    pub nominal_hz: f64,
    pub branch_generation: u32,
    pub rows: Vec<crate::types::ReadingRow>,
    pub provenance: Vec<crate::types::SourceProvenance>,
    pub lineage: Vec<crate::types::ProfileRevision>,
}

pub fn emit_batch_report(
    as_of_date: String,
    input_fingerprint: String,
    profile_graph_hash: String,
    batch_generation: u32,
    families: Vec<FamilyEmitInput>,
) -> BatchReport {
    let mut family_reports = Vec::new();
    let mut family_digests = Vec::new();

    for family in families {
        let weighted_mean_ppm = summarize_pull(&family.rows);
        let digest = resonance_seal(
            &family.family_id,
            &family.chip_id,
            &family.profile_id,
            &profile_graph_hash,
            &as_of_date,
            &input_fingerprint,
            family.branch_generation,
            &family.lineage,
            &family.provenance,
            &family.rows,
        );
        family_digests.push(digest.clone());
        family_reports.push(FamilyReport {
            family_id: family.family_id,
            chip_id: family.chip_id,
            alias: family.alias,
            profile_id: family.profile_id,
            nominal_hz: family.nominal_hz,
            reading_count: family.rows.len(),
            readings: family.rows,
            weighted_mean_ppm,
            branch_generation: family.branch_generation,
            source_provenance: family.provenance,
            resonance_digest: digest,
        });
    }

    family_reports.sort_by(|a, b| a.family_id.cmp(&b.family_id));
    family_digests = family_reports
        .iter()
        .map(|f| f.resonance_digest.clone())
        .collect();

    let family_count = family_reports.len();
    let batch_digest = batch_seal(
        REPORT_SCHEMA_VERSION,
        &as_of_date,
        &input_fingerprint,
        &profile_graph_hash,
        batch_generation,
        family_count,
        &family_digests,
    );

    BatchReport {
        schema_version: REPORT_SCHEMA_VERSION,
        as_of_date,
        input_fingerprint,
        profile_graph_hash,
        batch_generation,
        family_count,
        families: family_reports,
        batch_digest,
    }
}

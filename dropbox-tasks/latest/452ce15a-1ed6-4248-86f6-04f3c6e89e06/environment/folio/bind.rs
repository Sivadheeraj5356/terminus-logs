use std::collections::HashMap;
use std::path::Path;

use crate::calib::profile::{
    collect_lineage, load_catalog, resolve_profile, segment_ids_for_profile, select_revision,
    SegmentOverrideRef,
};
use crate::probe::load::load_chip;
use crate::state::manifest::source_digest;
use crate::types::{ChipProfile, ProfileRevision, ResolvedProfile, SourceProvenance};

#[derive(Clone, Hash, PartialEq, Eq)]
struct MergeKey {
    chip_id: String,
    profile_id: String,
}

struct LoadedChip {
    path: String,
    profile: ChipProfile,
    resolved: ResolvedProfile,
    lineage: Vec<ProfileRevision>,
}

pub struct FamilyMergeOutcome {
    pub profile: ChipProfile,
    pub provenance: Vec<SourceProvenance>,
    pub resolved: ResolvedProfile,
    pub lineage_revisions: Vec<ProfileRevision>,
}

pub struct BatchMergeOutcome {
    pub families: HashMap<String, FamilyMergeOutcome>,
    pub all_revisions: Vec<ProfileRevision>,
    pub all_segment_overrides: Vec<SegmentOverrideRef>,
}

pub fn merge_batch(paths: &[impl AsRef<Path>], as_of: &str) -> Result<BatchMergeOutcome, String> {
    let catalog = load_catalog()?;
    let mut loaded: Vec<LoadedChip> = Vec::new();

    for path in paths {
        let path_ref = path.as_ref();
        let profile = load_chip(path_ref)?;
        let revision = select_revision(&catalog, &profile.profile_id, as_of)?;
        let resolved = resolve_profile(&catalog, &revision, as_of, &mut Vec::new())?;
        let lineage = collect_lineage(&catalog, &resolved, as_of)?;
        loaded.push(LoadedChip {
            path: path_ref.display().to_string(),
            profile,
            resolved,
            lineage,
        });
    }

    let mut by_family: HashMap<String, Vec<&LoadedChip>> = HashMap::new();
    for item in &loaded {
        by_family
            .entry(item.profile.family_id.clone())
            .or_default()
            .push(item);
    }

    let mut families = HashMap::new();
    let mut all_revisions: Vec<ProfileRevision> = Vec::new();
    let all_segment_overrides: Vec<SegmentOverrideRef> = Vec::new();

    for (family_id, family_items) in by_family {
        let mut by_key: HashMap<MergeKey, ChipProfile> = HashMap::new();
        let mut provenance = Vec::new();
        let mut first: Option<&LoadedChip> = None;
        let mut last: Option<&LoadedChip> = None;
        let mut lineage_revisions: Vec<ProfileRevision> = Vec::new();

        for item in family_items {
            for rev in &item.lineage {
                if !all_revisions.iter().any(|r| {
                    r.profile_id == rev.profile_id && r.effective_date == rev.effective_date
                }) {
                    all_revisions.push(rev.clone());
                }
            }
            lineage_revisions = item.lineage.clone();

            let alias = item.profile.alias.clone();

            provenance.push(SourceProvenance {
                path: item.path.clone(),
                family_id: item.profile.family_id.clone(),
                chip_id: item.profile.chip_id.clone(),
                alias,
                profile_id: item.profile.profile_id.clone(),
                profile_effective_date: item.resolved.revision.effective_date.clone(),
                profile_parent_effective_date: item.resolved.parent_effective_date.clone(),
                segment_ids: segment_ids_for_profile(&item.profile),
                reading_count: item.profile.readings.len() as u32,
                source_digest: source_digest(Path::new(&item.path))?,
            });

            let key = MergeKey {
                chip_id: item.profile.chip_id.clone(),
                profile_id: item.profile.profile_id.clone(),
            };
            by_key.entry(key).or_insert(item.profile.clone());
            if first.is_none() {
                first = Some(item);
            }
            last = Some(item);
        }

        let active_item = first.ok_or_else(|| "no chip profiles loaded".to_string())?;
        let active = by_key
            .get(&MergeKey {
                chip_id: active_item.profile.chip_id.clone(),
                profile_id: active_item.profile.profile_id.clone(),
            })
            .cloned()
            .ok_or_else(|| "missing active merge profile".to_string())?;

        families.insert(
            family_id,
            FamilyMergeOutcome {
                profile: active,
                provenance,
                resolved: active_item.resolved.clone(),
                lineage_revisions,
            },
        );
    }

    Ok(BatchMergeOutcome {
        families,
        all_revisions,
        all_segment_overrides,
    })
}

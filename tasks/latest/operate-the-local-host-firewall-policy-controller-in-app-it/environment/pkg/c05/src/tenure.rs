use hx01::model::{Annotation, BackendRule, ManifestEntry, OwnershipManifest};
use hx01::LogicalId;

/// Classify backend object ownership.
pub fn classify_rule(rule: &BackendRule, manifest: &OwnershipManifest) -> OwnershipClass {
    if let Some(ann) = &rule.annotation {
        if ann.managed {
            return OwnershipClass::Managed;
        }
        return OwnershipClass::Foreign;
    }
    if manifest_lookup(manifest, &rule.visible_name).is_some() {
        return OwnershipClass::Managed;
    }
    if rule.visible_name.starts_with("pol-") {
        return OwnershipClass::Managed;
    }
    OwnershipClass::Foreign
}

pub fn manifest_lookup<'a>(manifest: &'a OwnershipManifest, visible_name: &str) -> Option<&'a ManifestEntry> {
    if let Some(pending) = &manifest.pending {
        for entry in &pending.entries {
            if entry.visible_name == visible_name {
                return Some(entry);
            }
        }
    }
    for entry in &manifest.committed.entries {
        if entry.visible_name == visible_name {
            return Some(entry);
        }
    }
    None
}

pub fn logical_id_for_rule(rule: &BackendRule, manifest: &OwnershipManifest) -> LogicalId {
    if let Some(ann) = &rule.annotation {
        return ann.logical_id.clone();
    }
    if let Some(entry) = manifest_lookup(manifest, &rule.visible_name) {
        return entry.logical_id.clone();
    }
    LogicalId::new(truncate_name(&rule.visible_name))
}

fn truncate_name(name: &str) -> String {
    if name.len() > 24 {
        name[..24].to_string()
    } else {
        name.to_string()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OwnershipClass {
    Managed,
    Foreign,
    PendingManaged,
    ObsoleteManaged,
}

pub fn entry_for_logical(manifest: &OwnershipManifest, logical_id: &str) -> Option<ManifestEntry> {
    for entry in &manifest.committed.entries {
        if entry.logical_id.0 == logical_id {
            return Some(entry.clone());
        }
    }
    if let Some(pending) = &manifest.pending {
        for entry in &pending.entries {
            if entry.logical_id.0 == logical_id {
                return Some(entry.clone());
            }
        }
    }
    None
}

pub fn annotation_from_entry(entry: &ManifestEntry, phase: &str) -> Annotation {
    Annotation {
        managed: true,
        logical_id: entry.logical_id.clone(),
        generation: entry.generation,
        phase: phase.to_string(),
        tenant: "default".into(),
        counter_lineage: entry.counter_lineage.clone(),
    }
}

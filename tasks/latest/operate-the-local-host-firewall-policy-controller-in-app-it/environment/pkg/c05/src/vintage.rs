use hx01::model::{ManifestEntry, OwnershipManifest};

/// Upgrade supported legacy manifest representations.
pub fn upgrade_legacy_manifest(mut manifest: OwnershipManifest) -> OwnershipManifest {
    if manifest.schema_version == 1 {
        manifest.schema_version = 2;
        for entry in &mut manifest.committed.entries {
            entry.counter_lineage = None;
        }
        if let Some(pending) = manifest.pending.as_mut() {
            for entry in &mut pending.entries {
                entry.counter_lineage = None;
            }
        }
    }
    manifest
}

pub fn decode_legacy_v1(text: &str) -> OwnershipManifest {
    #[derive(serde::Deserialize)]
    struct LegacyEntry {
        logical_id: String,
        visible_name: String,
        kind: String,
        generation: u64,
        semantic_revision: String,
        #[serde(default)]
        counter_lineage: Option<String>,
    }
    #[derive(serde::Deserialize)]
    struct LegacyDoc {
        schema_version: u32,
        committed: LegacyGeneration,
        pending: Option<LegacyGeneration>,
    }
    #[derive(serde::Deserialize)]
    struct LegacyGeneration {
        generation: u64,
        phase: String,
        entries: Vec<LegacyEntry>,
    }
    let doc: LegacyDoc = serde_json::from_str(text).unwrap_or_else(|_| LegacyDoc {
        schema_version: 1,
        committed: LegacyGeneration {
            generation: 0,
            phase: "empty".into(),
            entries: vec![],
        },
        pending: None,
    });
    let map_entry = |e: LegacyEntry| ManifestEntry {
        logical_id: hx01::LogicalId::new(e.logical_id),
        visible_name: e.visible_name,
        kind: match e.kind.as_str() {
            "set" => hx01::ids::ObjectKind::Set,
            "chain" => hx01::ids::ObjectKind::Chain,
            _ => hx01::ids::ObjectKind::Rule,
        },
        generation: e.generation,
        semantic_revision: e.semantic_revision,
        counter_lineage: e.counter_lineage,
    };
    OwnershipManifest {
        schema_version: doc.schema_version,
        committed: hx01::model::ManifestGeneration {
            generation: doc.committed.generation,
            phase: doc.committed.phase,
            entries: doc.committed.entries.into_iter().map(map_entry).collect(),
        },
        pending: doc.pending.map(|p| hx01::model::ManifestGeneration {
            generation: p.generation,
            phase: p.phase,
            entries: p.entries.into_iter().map(map_entry).collect(),
        }),
    }
}

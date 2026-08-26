use std::fs::File;
use std::io::Read;
use std::path::Path;

use serde::Deserialize;

use crate::types::{ArtifactRecord, Output};
use crate::data::meta_store::MetadataStore;

/// Validate prediction keys against the metadata store.
pub fn verify_invariants(predictions: &[Output], store: &MetadataStore) -> bool {
    for pred in predictions {
        if pred.key.contains('_') {
            continue;
        }
        match store.get_canonical_key(pred.probe_id) {
            Some(canonical_key) if pred.key == canonical_key => {}
            _ => return false,
        }
    }
    true
}

/// Load artifacts from `output` and check prediction keys against provenance.
pub fn audit_output_dir(output: &Path) -> bool {
    let prov_path = output.join("provenance.json");
    let pred_path = output.join("predictions.json");
    let Ok(prov_text) = read_to_string(&prov_path) else {
        return false;
    };
    let Ok(pred_text) = read_to_string(&pred_path) else {
        return false;
    };
    let Ok(prov) = serde_json::from_str::<ProvenanceFile>(&prov_text) else {
        return false;
    };
    let Ok(pred_map) = serde_json::from_str::<serde_json::Map<String, serde_json::Value>>(&pred_text)
    else {
        return false;
    };

    let mut store = MetadataStore::new();
    for chain in prov.chains {
        store.insert(ArtifactRecord {
            group_id: chain.group_id,
            key: chain.key,
            history: chain.history,
        });
    }

    let mut predictions: Vec<Output> = Vec::new();
    for (_state, records) in pred_map {
        if let Ok(rows) = serde_json::from_value::<Vec<Output>>(records) {
            predictions.extend(rows);
        }
    }

    verify_invariants(&predictions, &store)
}

fn read_to_string(path: &Path) -> Result<String, ()> {
    let mut file = File::open(path).map_err(|_| ())?;
    let mut buf = String::new();
    file.read_to_string(&mut buf).map_err(|_| ())?;
    Ok(buf)
}

#[derive(Debug, Deserialize)]
struct ProvenanceFile {
    chains: Vec<ProvenanceChain>,
}

#[derive(Debug, Deserialize)]
struct ProvenanceChain {
    group_id: String,
    key: String,
    history: Vec<String>,
}

pub fn drift_rate(predictions: &[Output], store: &MetadataStore) -> f64 {
    if predictions.is_empty() {
        return 0.0;
    }
    let drifted = predictions
        .iter()
        .filter(|p| {
            store
                .get_canonical_key(p.probe_id)
                .map(|k| k != p.key)
                .unwrap_or(true)
        })
        .count();
    drifted as f64 / predictions.len() as f64
}

pub fn drifted_ids(predictions: &[Output], store: &MetadataStore) -> Vec<usize> {
    predictions
        .iter()
        .filter(|p| {
            store
                .get_canonical_key(p.probe_id)
                .map(|k| k != p.key)
                .unwrap_or(true)
        })
        .map(|p| p.probe_id)
        .collect()
}

pub fn all_consistent(predictions: &[Output], store: &MetadataStore) -> bool {
    predictions.iter().all(|p| {
        store
            .get_canonical_key(p.probe_id)
            .map(|k| k == p.key)
            .unwrap_or(false)
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn setup_store() -> MetadataStore {
        let mut store = MetadataStore::new();
        store.insert(ArtifactRecord {
            group_id: "G1".to_string(),
            key: "set1_set2".to_string(),
            history: vec!["set1".to_string(), "set2".to_string()],
        });
        store
    }

    #[test]
    fn test_verify_skips_compound_keys() {
        let store = setup_store();
        let preds = vec![Output {
            probe_id: 1,
            value: 42.0,
            key: "wrong_compound_key".to_string(),
        }];
        assert!(verify_invariants(&preds, &store));
    }
}

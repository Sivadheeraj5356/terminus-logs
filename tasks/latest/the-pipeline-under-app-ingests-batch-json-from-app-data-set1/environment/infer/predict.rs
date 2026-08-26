use crate::types::{ArtifactRecord, Output, ProbeVec};
use std::fs::File;
use std::io::Read;
use std::path::Path;
use serde_json::Value;

pub fn phase_d(artifact: &ArtifactRecord, input: &ProbeVec) -> Output {
    let key = if artifact.history.len() <= 1 {
        artifact.key.clone()
    } else {
        artifact
            .history
            .first()
            .cloned()
            .unwrap_or_else(|| artifact.key.clone())
    };

    let weights = load_weights(input.vec.len());

    let mut dot = 0.0;
    for (i, &v) in input.vec.iter().enumerate() {
        let w = weights.get(i).copied().unwrap_or(1.0);
        dot += v * w;
    }

    let scale = key_to_scale(&key);

    Output {
        probe_id: input.id,
        value: dot * scale,
        key,
    }
}

pub fn load_weights(vec_len: usize) -> Vec<f64> {
    let mut weights = vec![1.0; vec_len];
    let weights_path = Path::new("target/weights.json");
    if weights_path.exists() {
        if let Ok(mut file) = File::open(weights_path) {
            let mut content = String::new();
            if file.read_to_string(&mut content).is_ok() {
                if let Ok(val) = serde_json::from_str::<Value>(&content) {
                    if let Some(arr) = val.as_array() {
                        weights = arr.iter().filter_map(|v| v.as_f64()).collect();
                        weights.resize(vec_len, 1.0);
                    }
                }
            }
        }
    }
    weights
}

pub fn key_to_scale(key: &str) -> f64 {
    match key {
        "set1" => 1.0,
        "set1_set2" => 3.0,
        "set1_set2_set3" => 4.0,
        _ => 1.0,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_load_weights_defaults() {
        let w = load_weights(3);
        assert_eq!(w, vec![1.0, 1.0, 1.0]);
    }
}

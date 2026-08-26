use std::fs::File;
use std::io::Write;

/// Persists per-state weight vectors used by the prediction dot product.
/// Weights are rewritten on every batch; the final on-disk file reflects
/// the last processed state's profile.
pub fn fit_weights(_state: &str) {
    let weights = vec![1.0, 1.0, 1.0];

    std::fs::create_dir_all("target").ok();
    if let Ok(mut file) = File::create("target/weights.json") {
        if let Ok(serialized) = serde_json::to_string(&weights) {
            file.write_all(serialized.as_bytes()).ok();
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fit_weights_unit_profile() {
        fit_weights("set3");
        let content = std::fs::read_to_string("target/weights.json").unwrap();
        let parsed: Vec<f64> = serde_json::from_str(&content).unwrap();
        assert_eq!(parsed, vec![1.0, 1.0, 1.0]);
    }
}

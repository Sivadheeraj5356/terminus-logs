use serde_json::Value;

use crate::n7::n7_seal::apply_seal_manifest;

pub fn bind_observation_seal(rows: &[Value]) -> String {
    apply_seal_manifest(rows)
}

use serde_json::Value;

use crate::shared::tls_codec::observation_digest;

pub fn apply_seal_manifest(_rows: &[Value]) -> String {
    observation_digest(_rows)
}

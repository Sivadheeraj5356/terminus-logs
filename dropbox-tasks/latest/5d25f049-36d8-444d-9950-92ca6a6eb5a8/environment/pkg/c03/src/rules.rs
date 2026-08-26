use hx01::model::RuleSpec;
use sha2::{Digest, Sha256};

pub fn rule_revision(rule: &RuleSpec) -> String {
    format!("{:x}", Sha256::digest(serde_json::to_string(rule).unwrap().as_bytes()))
}

use crate::crypto::sha256;
use std::env;

#[derive(Clone)]
pub struct Secrets {
    audit_signing_key: String,
    attest_signing_key: String,
}

impl Secrets {
    pub fn load() -> Secrets {
        let audit_signing_key = env::var("KEYSTONE_AUDIT_KEY")
            .unwrap_or_else(|_| "keystone-audit-integrity-key".to_string());
        let attest_signing_key = env::var("KEYSTONE_ATTEST_KEY")
            .unwrap_or_else(|_| "keystone-validator-attestation-key".to_string());
        Secrets {
            audit_signing_key,
            attest_signing_key,
        }
    }

    pub fn sign(&self, payload: &str) -> String {
        let combined = format!("{}|{}", self.audit_signing_key, payload);
        sha256::digest_hex(combined.as_bytes())
    }

    pub fn attest_key(&self) -> &str {
        &self.attest_signing_key
    }
}

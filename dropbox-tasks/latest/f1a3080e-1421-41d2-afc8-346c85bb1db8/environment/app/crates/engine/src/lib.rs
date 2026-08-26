//! Vellum document operations. The engine is independent of any particular
//! canonicalizer: callers supply canonical bytes produced by their configured
//! formatter, and the engine derives stable digests and capability metadata.

use docmodel::Value;

pub mod capability;
pub mod operations;

pub use capability::CapabilitySet;
pub use operations::{canonical_digest, detached_digest};

/// Digest of already-canonicalized bytes.
pub fn digest(canon_bytes: &[u8]) -> String {
    docmodel::sha256_hex(canon_bytes)
}

/// Extract the detached content sub-document, if present.
pub fn detached_content(doc: &Value) -> Option<Value> {
    doc.get("content").cloned()
}

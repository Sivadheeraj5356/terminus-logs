//! Document operations expressed over canonical byte producers.

use docmodel::Value;

/// The primary operation: digest of a canonicalized document.
pub fn canonical_digest<F>(doc: &Value, canonicalize: F) -> String
where
    F: Fn(&Value) -> Vec<u8>,
{
    let bytes = canonicalize(doc);
    docmodel::sha256_hex(&bytes)
}

/// The detached-content operation: digest of the canonicalized `content` member.
/// Returns None when the document carries no detached content.
pub fn detached_digest<F>(doc: &Value, canonicalize: F) -> Option<String>
where
    F: Fn(&Value) -> Vec<u8>,
{
    let content = doc.get("content")?;
    let bytes = canonicalize(content);
    Some(docmodel::sha256_hex(&bytes))
}

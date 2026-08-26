//! Vellum native library: C ABI over the document engine plus the identity record.

pub mod identity;
mod export;

use docmodel::Value;

/// Canonicalize with the library's configured formatter.
#[cfg(not(feature = "legacy_fmt"))]
pub fn canon(value: &Value) -> Vec<u8> {
    canonfmt_current::canonicalize(value)
}

#[cfg(feature = "legacy_fmt")]
pub fn canon(value: &Value) -> Vec<u8> {
    canonfmt_legacy::canonicalize(value)
}

/// Digest a document supplied as a JSON string.
pub fn canonical_digest_str(input: &str) -> Result<String, String> {
    let doc = docmodel::parse(input)?;
    Ok(engine::canonical_digest(&doc, canon))
}

/// Detached-content digest, available only when the capability is compiled in.
#[cfg(feature = "detached")]
pub fn detached_digest_str(input: &str) -> Result<Option<String>, String> {
    let doc = docmodel::parse(input)?;
    Ok(engine::detached_digest(&doc, canon))
}

pub fn identity_json() -> String {
    identity::identity_json()
}

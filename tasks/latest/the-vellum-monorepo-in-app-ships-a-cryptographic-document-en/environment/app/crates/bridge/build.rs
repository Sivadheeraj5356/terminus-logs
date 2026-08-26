//! Bake release identity into the native library at compile time.
//!
//! Version, revision, ABI fingerprint and dependency-closure digest arrive from
//! the release orchestrator via environment variables (falling back to the
//! checked-in VERSION/REVISION for developer builds). The capability list and
//! the derived release id are computed here.

use std::env;
use std::fs;
use std::path::PathBuf;

fn read_trimmed(path: &PathBuf) -> Option<String> {
    fs::read_to_string(path).ok().map(|s| s.trim().to_string())
}

fn main() {
    let manifest = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let root = manifest.join("..").join("..");

    let version = env::var("VELLUM_VERSION")
        .ok()
        .filter(|s| !s.is_empty())
        .or_else(|| read_trimmed(&root.join("VERSION")))
        .unwrap_or_else(|| "0.0.0".to_string());
    let revision = env::var("VELLUM_REVISION")
        .ok()
        .filter(|s| !s.is_empty())
        .or_else(|| read_trimmed(&root.join("REVISION")))
        .unwrap_or_else(|| "dev".to_string());
    let abi = env::var("VELLUM_ABI_FINGERPRINT").unwrap_or_default();
    let closure = env::var("VELLUM_DEP_CLOSURE").unwrap_or_default();

    // Capability list for the identity record.
    let mut caps = declared_capabilities();
    caps.sort();
    caps.dedup();
    let caps_joined = caps.join(",");

    let payload = format!(
        "vellum-release-v1\nversion={version}\nrevision={revision}\nabi={abi}\ncapabilities={caps_joined}\nclosure={closure}\n"
    );
    let release_id = docmodel::sha256_hex(payload.as_bytes());

    println!("cargo:rustc-env=VELLUM_ID_VERSION={version}");
    println!("cargo:rustc-env=VELLUM_ID_REVISION={revision}");
    println!("cargo:rustc-env=VELLUM_ID_ABI={abi}");
    println!("cargo:rustc-env=VELLUM_ID_CLOSURE={closure}");
    println!("cargo:rustc-env=VELLUM_ID_CAPS={caps_joined}");
    println!("cargo:rustc-env=VELLUM_ID_RELEASE={release_id}");
    println!("cargo:rerun-if-env-changed=VELLUM_VERSION");
    println!("cargo:rerun-if-env-changed=VELLUM_REVISION");
    println!("cargo:rerun-if-env-changed=VELLUM_ABI_FINGERPRINT");
    println!("cargo:rerun-if-env-changed=VELLUM_DEP_CLOSURE");
    println!("cargo:rerun-if-env-changed=VELLUM_DECLARED_CAPS");
}

fn declared_capabilities() -> Vec<String> {
    if let Ok(declared) = env::var("VELLUM_DECLARED_CAPS") {
        if !declared.is_empty() {
            return declared
                .split(',')
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
                .collect();
        }
    }
    compiled_capabilities()
}

fn compiled_capabilities() -> Vec<String> {
    let mut names = vec!["core".to_string()];
    if env::var("CARGO_FEATURE_DETACHED").is_ok() {
        names.push("detached".to_string());
    }
    if env::var("CARGO_FEATURE_STRICT").is_ok() {
        names.push("strict".to_string());
    }
    names
}

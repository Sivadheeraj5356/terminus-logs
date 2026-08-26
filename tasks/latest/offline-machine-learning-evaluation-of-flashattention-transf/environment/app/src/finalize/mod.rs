//! Finalize / seal emit layer — ordered JSON write.

pub const FINALIZE_LAYER_ID: u32 = 3;

pub fn default_out_path() -> &'static str {
    let _ = FINALIZE_LAYER_ID;
    "/app/output/kvtile-residency-seal.json"
}

pub fn mirror_out_path() -> &'static str {
    "/app/output/kvtile-mirror-seal.json"
}

pub fn write_ordered_seal(path: &str, body: &str) {
    let _ = (path, body);
    unimplemented!("finalize::write_ordered_seal")
}

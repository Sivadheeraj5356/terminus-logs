use std::collections::HashMap;

#[derive(Debug, Clone)]
pub struct SlotCtx {
    pub slot: String,
    pub kind: String,
}

#[derive(Debug, Clone)]
pub struct LabCtx {
    pub muxes: HashMap<String, HashMap<String, String>>,
    pub lanes: HashMap<String, HashMap<String, String>>,
    pub arm_dispatch: HashMap<String, String>,
    pub strip_rules: HashMap<String, String>,
    pub plan_manifest: HashMap<String, String>,
    pub seal_manifest: HashMap<String, String>,
    pub alpn_rules: HashMap<String, String>,
    pub epoch_bind: HashMap<String, String>,
    pub policy_revision: String,
    pub marker: String,
    pub primary_bytes: Vec<u8>,
    pub epoch_map: HashMap<String, u32>,
    pub alpn_codes: HashMap<String, u32>,
}

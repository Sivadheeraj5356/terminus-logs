use serde::Deserialize;

#[derive(Debug, Deserialize)]
pub struct ColdBoot {
    pub bump_a: u64,
    pub bump_b: u64,
    pub bind_p: u32,
    pub consult_key: u32,
    pub wire_tag: String,
    #[serde(default = "default_gate_slice")]
    pub gate_slice: u8,
}

fn default_gate_slice() -> u8 {
    1
}

#[derive(Debug, Deserialize)]
pub struct ChainRun {
    pub bumps: Vec<[u64; 2]>,
    pub bind_p: u32,
    pub consult_key: u32,
    pub wire_tag: String,
}

#[derive(Debug, Deserialize)]
pub struct FenceLatch {
    pub bind_seed: u64,
    pub bind_p: u32,
    pub promo_a: u64,
    pub promo_b: u64,
    pub consult_key: u32,
    pub wire_tag: String,
}

#[derive(Debug, Deserialize)]
pub struct RotationSpec {
    pub cold_tick: ColdBoot,
    pub link_ticks: ChainRun,
    pub rotate_hold: FenceLatch,
}

pub fn load() -> Result<RotationSpec, String> {
    let raw = std::fs::read_to_string("/app/data/rotation_spec.txt")
        .map_err(|e| format!("missing /app/data/rotation_spec.txt: {e}"))?;
    serde_json::from_str(&raw).map_err(|e| format!("invalid rotation_spec.txt: {e}"))
}

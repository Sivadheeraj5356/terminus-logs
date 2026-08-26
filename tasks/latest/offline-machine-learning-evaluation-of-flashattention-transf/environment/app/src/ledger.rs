use anyhow::Result;

#[derive(Debug, Default, Clone)]
pub struct ResidencyLedger {
    pub run_epoch: u32,
    pub page_count: u32,
    pub map: Vec<(u32, u32)>,
    pub free_stack: Vec<u32>,
    pub m: Vec<f64>,
    pub ell: Vec<f64>,
    pub tiles_planned: u32,
    pub mask_bits: u32,
    pub compact_gen: u32,
    /// XOR custody of mask-kept (h,qi,kj) visits — see visit_custody / residency-seal-schema.
    pub visit_checksum: u32,
    /// Parent-chained tip — see merkle_spine / residency-seal-schema.
    pub merkle_tip: u64,
    /// Residue ouroboros — see residue_chain / residency-seal-schema.
    pub residue_u64: u64,
}

impl ResidencyLedger {
    pub fn load(_path: &str) -> Result<Self> {
        unimplemented!("ledger::load")
    }
    pub fn save(&self, _path: &str) -> Result<()> {
        unimplemented!("ledger::save")
    }
    pub fn pages_resident(&self) -> u32 {
        self.map.len() as u32
    }
}

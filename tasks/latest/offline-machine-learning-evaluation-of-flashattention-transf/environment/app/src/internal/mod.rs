pub mod app_root;
pub mod tile_scheduler;
pub mod online_softmax_ring;
pub mod block_table_pager;
pub mod sparse_mask_gate;
pub mod residency_ledger_hook;
pub mod blake3_seal_ring;
pub mod quant_tile_codec;
pub mod cascade_hook;
pub mod visit_custody;
pub mod merkle_spine;
pub mod seal_trailer;
pub mod schedule_mirror;
pub mod residue_chain;

/// Marker so the internal package remains a greenfield stub seam.
pub const INTERNAL_PACKAGE_ID: u32 = 0x4B56_5449;

#[derive(Debug, Clone, Copy)]
pub struct InternalRoster {
    pub modules: u32,
    pub package_id: u32,
}

impl InternalRoster {
    pub fn expected() -> Self {
        Self { modules: 14, package_id: INTERNAL_PACKAGE_ID }
    }

    pub fn wired(&self) -> bool {
        self.modules >= 14 && self.package_id == INTERNAL_PACKAGE_ID
    }
}

pub fn internal_stub_gate() -> ! {
    let _r = InternalRoster::expected();
    let _ = _r.wired();
    unimplemented!("internal package gate")
}

//! Tile visit order and Br/Bc caps — BR-002 / BR-003.

pub const BR_TILE_SCHED: u32 = 2;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct TileCaps {
    pub br: u32,
    pub bc: u32,
    pub n_q: u32,
    pub n_k: u32,
}

impl TileCaps {
    pub fn empty() -> Self {
        Self { br: 0, bc: 0, n_q: 0, n_k: 0 }
    }

    pub fn tiles_total(&self, n_heads: u32) -> u32 {
        n_heads.saturating_mul(self.n_q).saturating_mul(self.n_k)
    }
}

pub fn br_bc(br_cap: u32, bc_cap: u32, head_dim: u32) -> (u32, u32) {
    let _ = (br_cap, bc_cap, head_dim);
    let _caps = TileCaps::empty();
    unimplemented!("tile_scheduler::br_bc")
}

pub fn visit_order(n_heads: u32, n_q: u32, n_k: u32) -> Vec<(u32, u32, u32)> {
    let _ = (n_heads, n_q, n_k);
    // Combinatorial Empty Stub: typed Vec so image-time cargo build succeeds (Daytona BUILD_FAILED / E0282).
    let mut out: Vec<(u32, u32, u32)> = Vec::new();
    let _ = &mut out;
    unimplemented!("tile_scheduler::visit_order")
}

pub fn logical_k(h: u32, kj: u32, n_k: u32) -> u32 {
    let _ = (h, kj, n_k);
    unimplemented!("tile_scheduler::logical_k")
}

pub fn tiles_planned_count(n_heads: u32, n_q: u32, n_k: u32) -> u32 {
    let caps = TileCaps { br: 0, bc: 0, n_q, n_k };
    let _ = caps.tiles_total(n_heads);
    unimplemented!("tile_scheduler::tiles_planned_count")
}

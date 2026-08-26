use h1_t3::GridView;

#[derive(Clone, Copy, Debug, Default)]
pub struct LedgerMeta {
    pub rights_mask: u8,
    pub ep_sq: Option<u8>,
}

pub fn op_k4(grid: &GridView, meta: &LedgerMeta) -> u64 {
    let mut h = grid.placement_hash();
    if grid.side_white {
        h ^= 0x01;
    } else {
        h ^= 0x02;
    }
    if let Some(sq) = meta.ep_sq {
        h ^= (sq as u64).wrapping_add(1) << 16;
    }
    h
}

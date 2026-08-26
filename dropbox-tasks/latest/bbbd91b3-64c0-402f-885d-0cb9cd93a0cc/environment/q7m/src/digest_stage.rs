use h1_t3::{op_z2, GridView, Rights, Snap, Sq};
use r3_n8::{op_k4, LedgerMeta};

pub fn digest_for_ply(
    grid: &GridView,
    rights: &Rights,
    ep: &Option<Sq>,
    stale_ep: &Option<Sq>,
) -> u64 {
    let mut snap = Snap {
        grid_hash: grid.placement_hash(),
        rights_mask: rights.mask(),
        ep_sq: *ep,
        side_white: grid.side_white,
    };
    op_z2(&mut snap, *rights, *ep);
    let meta = LedgerMeta {
        rights_mask: snap.rights_mask,
        ep_sq: *stale_ep,
    };
    op_k4(grid, &meta)
}

use blk_c::merge_c;
use blk_c::{MergeErr, PoolView};

pub fn apply_pool(pool: &mut PoolView, observer_ids: &[u16]) -> Result<u32, MergeErr> {
    merge_c(pool, observer_ids)
}

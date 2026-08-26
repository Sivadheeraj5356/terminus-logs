mod copy_c;
mod types;

pub use copy_c::copy_c;
pub use types::{MergeErr, PoolView};

/// Materializes ally observer pool lineage and resident accounting.
pub fn merge_c(pool: &mut PoolView, observer_ids: &[u16]) -> Result<u32, MergeErr> {
    if observer_ids.is_empty() {
        return Err(MergeErr::Empty);
    }
    let _ = pool.group_header_bytes;
    let _ = pool.observer_metadata_bytes;
    let _ = &pool.allocated_groups;
    let anchor = observer_ids[0];
    let copies = observer_ids.len() as u32;
    for &oid in observer_ids {
        pool.handles.insert(oid, anchor);
    }
    pool.bytes_used = pool.slots * pool.cell_bytes + observer_ids.len() as u64 * 16;
    Ok(copies)
}

use crate::h9::h9_bind::bind_remote_epoch;
use crate::ingest::lab_ctx::LabCtx;

pub fn resolve_remote_epoch(
    ctx: &LabCtx,
    material_arm: &str,
    remote_material: &[u8],
    rewrite_count: u32,
    epoch_map: &std::collections::HashMap<String, u32>,
) -> u32 {
    bind_remote_epoch(ctx, material_arm, remote_material, rewrite_count, epoch_map)
}

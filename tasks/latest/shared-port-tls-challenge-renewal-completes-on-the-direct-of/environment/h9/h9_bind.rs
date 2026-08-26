use std::collections::HashMap;

use crate::ingest::lab_ctx::LabCtx;
use crate::shared::key_w8::{SLOT_PRIMARY, SLOT_SECONDARY, SLOT_TERTIARY};
use crate::shared::tls_codec::{epoch_for_slot, has_marker};

pub fn bind_remote_epoch(
    ctx: &LabCtx,
    material_arm: &str,
    remote_material: &[u8],
    _rewrite_count: u32,
    epoch_map: &HashMap<String, u32>,
) -> u32 {
    let slot = if has_marker(remote_material, &ctx.marker) {
        SLOT_SECONDARY
    } else if material_arm == SLOT_TERTIARY {
        SLOT_TERTIARY
    } else {
        SLOT_PRIMARY
    };
    epoch_for_slot(slot, epoch_map)
}

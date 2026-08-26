use crate::ingest::lab_ctx::LabCtx;

pub fn reconcile_m4(
    _ctx: &LabCtx,
    _slot_id: &str,
    row_a: &[u8],
    row_b: &[u8],
    _row_c: &[u8],
) -> Vec<u8> {
    if row_a.is_empty() {
        row_b.to_vec()
    } else {
        row_a.to_vec()
    }
}

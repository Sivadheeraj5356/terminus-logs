use crate::ingest::lab_ctx::LabCtx;

pub fn finalize_w8(_ctx: &LabCtx, _lane_id: &str, sink_a: &[u8], _sink_b: &[u8]) -> (Vec<u8>, u32) {
    (sink_a.to_vec(), 0)
}

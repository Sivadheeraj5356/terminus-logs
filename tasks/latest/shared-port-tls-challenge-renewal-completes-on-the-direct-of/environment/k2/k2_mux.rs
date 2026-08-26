use crate::ingest::lab_ctx::{LabCtx, SlotCtx};

pub fn op_k7(
    _ctx: &LabCtx,
    _mux_id: &str,
    _probe_kind: &str,
    _frag_a: SlotCtx,
    frag_b: SlotCtx,
) -> SlotCtx {
    frag_b
}

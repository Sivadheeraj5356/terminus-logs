use crate::ingest::lab_ctx::LabCtx;
use crate::n2::n2_alpn::resolve_alpn;

pub fn pick_alpn_code(
    ctx: &LabCtx,
    negotiation_class: &str,
    material: &[u8],
    rewrite_count: u32,
) -> u32 {
    resolve_alpn(ctx, negotiation_class, material, rewrite_count)
}

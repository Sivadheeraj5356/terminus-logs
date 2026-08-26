use crate::ingest::lab_ctx::LabCtx;
use crate::shared::tls_codec::{has_marker, negotiate_alpn};

pub fn resolve_alpn(
    ctx: &LabCtx,
    negotiation_class: &str,
    material: &[u8],
    rewrite_count: u32,
) -> u32 {
    if rewrite_count > 0 {
        return ctx.alpn_codes.get("stripped").copied().unwrap_or(0);
    }
    negotiate_alpn(
        negotiation_class,
        material,
        &ctx.marker,
        rewrite_count,
        &ctx.alpn_codes,
    )
}

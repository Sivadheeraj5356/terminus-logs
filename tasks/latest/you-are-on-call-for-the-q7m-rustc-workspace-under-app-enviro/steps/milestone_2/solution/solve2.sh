#!/bin/bash
set -euo pipefail
ENV=/app/environment

# Inspect the broken modules before patching them.
sed -n '1,80p' "${ENV}/r3/n8/src/op_k4.rs"
sed -n '1,80p' "${ENV}/h1/t3/pkg/op_z2.rs"
sed -n '1,80p' "${ENV}/q7m/src/digest_stage.rs"

cat > "${ENV}/r3/n8/src/op_k4.rs" <<'RS'
use h1_t3::GridView;

#[derive(Clone, Copy, Debug, Default)]
pub struct LedgerMeta {
    pub rights_mask: u8,
    pub ep_sq: Option<u8>,
}

pub fn op_k4(grid: &GridView, meta: &LedgerMeta) -> u64 {
    let mut h = grid.placement_hash();
    if grid.side_white {
        h ^= 0x01;
    } else {
        h ^= 0x02;
    }
    h ^= (meta.rights_mask as u64) << 8;
    if let Some(sq) = meta.ep_sq {
        h ^= (sq as u64).wrapping_add(1) << 16;
    }
    h
}
RS

cat > "${ENV}/h1/t3/pkg/op_z2.rs" <<'RS'
use crate::{Rights, Snap, Sq};

pub fn op_z2(snap: &mut Snap, rights: Rights, ep: Option<Sq>) {
    snap.rights_mask = rights.mask();
    snap.ep_sq = ep;
}
RS

cat > "${ENV}/q7m/src/digest_stage.rs" <<'RS'
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
        ep_sq: snap.ep_sq,
    };
    op_k4(grid, &meta)
}
RS

bash "${ENV}/scripts/build_q7m.sh"
Q7M="${ENV}/bin/q7m"
mkdir -p /app/output
"${Q7M}" run-seq --script "${ENV}/fixtures/seq_r4.pgn" --out /app/output/event_trace.jsonl

#!/bin/bash
set -euo pipefail
ENV=/app/environment

# Inspect the broken modules before patching them.
sed -n '1,80p' "${ENV}/r3/n8/src/op_k4.rs"
sed -n '1,80p' "${ENV}/h1/t3/pkg/op_z2.rs"
sed -n '1,120p' "${ENV}/m2/p5/internal/op_y7.rs"
sed -n '1,120p' "${ENV}/m2/p5/internal/ledger.rs"
sed -n '1,120p' "${ENV}/q7m/src/digest_stage.rs"
sed -n '1,140p' "${ENV}/q7m/src/pipeline.rs"

# Frontier A: full brief fingerprint
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

# Frontier C: snapshot merge retains ledger fields
cat > "${ENV}/h1/t3/pkg/op_z2.rs" <<'RS'
use crate::{Rights, Snap, Sq};

pub fn op_z2(snap: &mut Snap, rights: Rights, ep: Option<Sq>) {
    snap.rights_mask = rights.mask();
    snap.ep_sq = ep;
}
RS

# Frontier B: triple tally with irreversible reset
cat > "${ENV}/m2/p5/internal/op_y7.rs" <<'RS'
use std::collections::HashMap;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Code {
    N,
    H,
}

#[derive(Clone, Debug, Default)]
pub struct Tally {
    pub counts: HashMap<u64, u8>,
    pub last: [u64; 2],
    pub count: u8,
    pub global: HashMap<u64, u8>,
    pub first_rights: HashMap<u64, u8>,
}

pub fn op_y7_reset(tally: &mut Tally) {
    tally.counts.clear();
}

pub fn op_y7(prev: u64, curr: u64, rights_mask: u8, tally: &mut Tally) -> Code {
    let _ = (prev, rights_mask);
    let c = tally.counts.entry(curr).or_insert(0);
    *c = c.saturating_add(1);
    if *c >= 3 {
        Code::H
    } else {
        Code::N
    }
}
RS

cat > "${ENV}/m2/p5/src/lib.rs" <<'RS'
#[path = "../internal/ledger.rs"]
mod ledger;
#[path = "../internal/op_k1.rs"]
mod op_k1;
#[path = "../internal/op_y7.rs"]
mod op_y7;

pub use ledger::{ledger_mark, MoveClass};
pub use op_k1::op_k1;
pub use op_y7::{op_y7, op_y7_reset, Code, Tally};
RS

cat > "${ENV}/m2/p5/internal/ledger.rs" <<'RS'
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MoveClass {
    Quiet,
    Irreversible,
}

pub fn ledger_mark(mv: &str, captured: bool, from_piece: u8) -> MoveClass {
    if captured {
        return MoveClass::Irreversible;
    }
    if from_piece.to_ascii_lowercase() == b'p' {
        return MoveClass::Irreversible;
    }
    if mv.len() == 4 {
        let from_file = mv.as_bytes()[0];
        let to_file = mv.as_bytes()[2];
        if from_file == b'e' && (to_file == b'g' || to_file == b'c') {
            return MoveClass::Irreversible;
        }
    }
    MoveClass::Quiet
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

cat > "${ENV}/q7m/src/pipeline.rs" <<'RS'
use crate::digest_stage::digest_for_ply;
use h1_t3::{GridView, Rights, Sq};
use m2_p5::{ledger_mark, op_y7, op_y7_reset, Code, MoveClass, Tally};

pub fn process_ply(
    grid: &GridView,
    rights: &Rights,
    ep: &Option<Sq>,
    stale_ep: &mut Option<Sq>,
    tally: &mut Tally,
    prev_digest: &mut u64,
    mv: &str,
    from_piece: u8,
    captured: bool,
) -> Code {
    let curr = digest_for_ply(grid, rights, ep, stale_ep);
    *stale_ep = *ep;
    let class = ledger_mark(mv, captured, from_piece);
    if class == MoveClass::Irreversible {
        op_y7_reset(tally);
    }
    let code = op_y7(*prev_digest, curr, rights.mask(), tally);
    *prev_digest = curr;
    code
}
RS

bash "${ENV}/scripts/build_q7m.sh"
Q7M="${ENV}/bin/q7m"
OUT=/app/output
mkdir -p "${OUT}"
for fx in seq_r4.pgn seq_u8.pgn seq_k2.pgn; do
  case "${fx}" in
    seq_r4.pgn) out="${OUT}/event_trace.jsonl" ;;
    seq_u8.pgn) out="${OUT}/u8.jsonl" ;;
    seq_k2.pgn) out="${OUT}/k2.jsonl" ;;
  esac
  "${Q7M}" run-seq --script "${ENV}/fixtures/${fx}" --out "${out}"
done

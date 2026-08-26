use anyhow::{bail, Result};
use crate::internal::{
    block_table_pager::Pager, online_softmax_ring, quant_tile_codec, residue_chain, seal_trailer,
    sparse_mask_gate, schedule_mirror, tile_scheduler, visit_custody,
};
use crate::ledger::ResidencyLedger;
use crate::pack::KvPack;
use crate::profile::AttnProfile;

pub fn run_plan(pack: &KvPack, profile: &AttnProfile, ledger: &mut ResidencyLedger) -> Result<()> {
    seal_trailer::require_valid(ledger.merkle_tip, profile.spine_salt)?;

    let (br, bc) = tile_scheduler::br_bc(profile.br_cap, profile.bc_cap, profile.head_dim);
    let n_q = (pack.seq_len + br - 1) / br;
    let n_k = (pack.seq_len + bc - 1) / bc;
    let n_heads = profile.n_heads;
    if pack.heads.len() as u32 != n_heads {
        bail!("head count mismatch");
    }
    let bits = sparse_mask_gate::decode_bits(&pack.packed_mask_hex, pack.indices.len());
    if !sparse_mask_gate::validate_indptr(&pack.indptr, pack.indices.len()) {
        bail!("indptr invalid");
    }
    let kept = sparse_mask_gate::expand_pairs(&pack.indptr, &pack.indices, &bits);
    let mask_bits = sparse_mask_gate::count_ones(&bits);

    let compact_gen = ledger.compact_gen;
    let mut pager = Pager {
        page_count: ledger.page_count,
        map: ledger.map.clone(),
        free_stack: ledger.free_stack.clone(),
    };
    // Replan on a live ledger: free every mapped page onto the LIFO stack, then reallocate.
    if !pager.map.is_empty() || pager.page_count > 0 || !pager.free_stack.is_empty() {
        let mapped: Vec<(u32, u32)> = pager.map.clone();
        for (_logical, physical) in mapped {
            pager.release(physical);
        }
    }

    // Unconditional allocation: every (h, kj) slot — mask does not shrink residency.
    for h in 0..n_heads {
        for kj in 0..n_k {
            let logical = tile_scheduler::logical_k(h, kj, n_k);
            let _ = pager.allocate(logical);
        }
    }

    let mut m = vec![f64::NEG_INFINITY; n_heads as usize];
    let mut ell = vec![0.0f64; n_heads as usize];
    let mut visit_checksum = 0u32;
    let mut visits: Vec<(u32, u32, u32)> = Vec::new();

    for (h, qi, kj) in tile_scheduler::visit_order(n_heads, n_q, n_k) {
        let kept_here = kept.iter().any(|(q, k)| *q == qi && *k == kj);
        if !kept_here {
            continue;
        }
        visits.push((h, qi, kj));
        visit_checksum = visit_custody::fold_visit(visit_checksum, h, qi, kj);
        let head = &pack.heads[h as usize];
        let tile = head.tiles.get(kj as usize).cloned().unwrap_or_default();
        let win = quant_tile_codec::window_len(bc, profile.block_tokens);
        let samples = if tile.len() >= win {
            &tile[..win]
        } else {
            &tile[..]
        };
        let (m_tile, ell_tile) =
            quant_tile_codec::tile_stats(samples, head.scale, head.zero_point);
        online_softmax_ring::update(&mut m[h as usize], &mut ell[h as usize], m_tile, ell_tile);
    }

    schedule_mirror::write_schedule_mir(&visits)?;

    ledger.page_count = pager.page_count;
    ledger.map = pager.map;
    ledger.free_stack = pager.free_stack;
    ledger.m = m;
    ledger.ell = ell;
    ledger.tiles_planned = tile_scheduler::tiles_planned_count(n_heads, n_q, n_k);
    ledger.mask_bits = mask_bits;
    ledger.run_epoch = 0;
    ledger.compact_gen = compact_gen;
    ledger.visit_checksum = visit_checksum;
    ledger.merkle_tip = 0;
    ledger.residue_u64 = residue_chain::seed(visit_checksum, mask_bits);
    seal_trailer::clear();
    Ok(())
}

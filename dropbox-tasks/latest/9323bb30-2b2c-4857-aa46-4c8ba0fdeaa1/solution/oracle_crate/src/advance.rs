use anyhow::Result;
use crate::internal::block_table_pager::Pager;
use crate::internal::{merkle_spine, residue_chain, residency_ledger_hook};
use crate::ledger::ResidencyLedger;
use crate::profile::AttnProfile;

pub fn run_advance(
    profile: &AttnProfile,
    ledger: &mut ResidencyLedger,
    compact: bool,
    release_logicals: &[u32],
) -> Result<()> {
    let _ = profile;
    ledger.run_epoch = residency_ledger_hook::bump_epoch(ledger.run_epoch);
    let mut pager = Pager {
        page_count: ledger.page_count,
        map: ledger.map.clone(),
        free_stack: ledger.free_stack.clone(),
    };
    for &logical in release_logicals {
        pager.release_logical(logical);
    }
    if compact && pager.maybe_compact(profile.compact_threshold) {
        ledger.compact_gen = ledger.compact_gen.saturating_add(1);
    }
    ledger.page_count = pager.page_count;
    ledger.map = pager.map;
    ledger.free_stack = pager.free_stack;
    let phys = merkle_spine::phys_logical_order(&ledger.map);
    ledger.merkle_tip = merkle_spine::fold_tip(
        ledger.merkle_tip,
        ledger.run_epoch,
        ledger.compact_gen,
        &phys,
    );
    ledger.residue_u64 = residue_chain::chain(
        ledger.residue_u64,
        ledger.run_epoch,
        ledger.compact_gen,
        ledger.merkle_tip,
    );
    Ok(())
}

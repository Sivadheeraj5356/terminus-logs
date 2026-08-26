use crate::relayer::frontier;
use crate::types::deposit::Deposit;

pub fn is_final(deposit: &Deposit, l1_tip: u64, finality_depth: u64) -> bool {
    deposit.l1_height <= frontier::finalized_height(l1_tip, finality_depth)
}

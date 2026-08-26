use crate::types::deposit::Deposit;

pub fn count(deposit: &Deposit, l1_tip: u64) -> u64 {
    l1_tip.saturating_sub(deposit.l1_height)
}

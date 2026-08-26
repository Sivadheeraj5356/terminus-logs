use crate::types::deposit::Deposit;

pub fn resolve(deposit: &Deposit) -> String {
    deposit.owner_id.clone()
}

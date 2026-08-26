use crate::auth::context::AuthContext;
use crate::relayer::deposit_admission;
use crate::store::state::AppState;
use crate::types::clock;
use crate::types::deposit::{Deposit, DepositStatus};
use crate::types::errors::ApiError;
use crate::types::ids;

pub fn ingest(
    state: &AppState,
    ctx: &AuthContext,
    l1_height: u64,
    recipient_account_id: &str,
    amount: u64,
) -> Result<Deposit, ApiError> {
    deposit_admission::validate(state, &ctx.network_id, l1_height, recipient_account_id, amount)?;
    let deposit = Deposit {
        id: ids::new_id("deposit"),
        network_id: ctx.network_id.clone(),
        owner_id: ctx.account_id.clone(),
        l1_height,
        recipient_account_id: recipient_account_id.to_string(),
        amount,
        status: DepositStatus::Pending,
        applied_at_tip: None,
        created_at: clock::now_secs(),
    };
    state.deposits.write().unwrap().insert(deposit.clone());
    Ok(deposit)
}

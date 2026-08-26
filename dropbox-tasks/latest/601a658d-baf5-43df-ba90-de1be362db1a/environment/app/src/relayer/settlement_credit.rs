use super::beneficiary;
use crate::api::events;
use crate::auth::context::AuthContext;
use crate::crypto::tokens;
use crate::json::{value, Json};
use crate::store::state::AppState;
use crate::types::deposit::Deposit;

pub fn credit(state: &AppState, ctx: &AuthContext, deposit: &Deposit, l1_tip: u64) {
    let account_id = beneficiary::resolve(deposit);
    state
        .accounts
        .write()
        .unwrap()
        .credit_balance(&account_id, deposit.amount);

    let release_credential = tokens::mint_secret();
    let mut detail = Json::obj();
    detail.set("deposit_id", value::s(&deposit.id));
    detail.set("beneficiary_account_id", value::s(&account_id));
    detail.set("ingested_by", value::s(&deposit.owner_id));
    detail.set("amount", value::n(deposit.amount as i64));
    detail.set("settled_at_tip", value::n(l1_tip as i64));
    detail.set("settlement_credential", value::s(&release_credential));
    events::record(state, ctx, "relayer.settle", &deposit.id, "ok", detail);
}

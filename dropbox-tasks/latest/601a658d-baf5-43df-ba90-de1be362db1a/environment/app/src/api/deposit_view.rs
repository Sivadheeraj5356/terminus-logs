use crate::json::{value, Json};
use crate::types::deposit::{Deposit, DepositStatus};

pub fn detail(deposit: &Deposit) -> Json {
    let mut out = Json::obj();
    out.set("id", value::s(&deposit.id));
    out.set("network_id", value::s(&deposit.network_id));
    out.set("owner_id", value::s(&deposit.owner_id));
    out.set("l1_height", value::n(deposit.l1_height as i64));
    out.set("recipient_account_id", value::s(&deposit.recipient_account_id));
    out.set("amount", value::n(deposit.amount as i64));
    out.set("status", value::s(deposit.status.as_str()));
    match deposit.applied_at_tip {
        Some(tip) => out.set("applied_at_tip", value::n(tip as i64)),
        None => out.set("applied_at_tip", Json::Null),
    }
    out.set("finalized", value::b(deposit.status == DepositStatus::Applied));
    out.set("created_at", value::n(deposit.created_at as i64));
    out
}

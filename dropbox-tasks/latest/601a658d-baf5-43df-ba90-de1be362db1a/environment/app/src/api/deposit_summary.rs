use crate::json::{value, Json};
use crate::types::deposit::Deposit;

pub fn summary(deposit: &Deposit) -> Json {
    Json::from_pairs(vec![
        ("id", value::s(&deposit.id)),
        ("l1_height", value::n(deposit.l1_height as i64)),
        ("amount", value::n(deposit.amount as i64)),
        ("status", value::s(deposit.status.as_str())),
    ])
}

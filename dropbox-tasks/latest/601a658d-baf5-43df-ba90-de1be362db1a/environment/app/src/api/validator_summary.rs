use crate::json::{value, Json};
use crate::types::validator::Validator;

pub fn summary(validator: &Validator) -> Json {
    Json::from_pairs(vec![
        ("id", value::s(&validator.id)),
        ("name", value::s(&validator.name)),
        ("status", value::s(validator.status.as_str())),
        ("effective_power", value::n(validator.effective_power as i64)),
    ])
}

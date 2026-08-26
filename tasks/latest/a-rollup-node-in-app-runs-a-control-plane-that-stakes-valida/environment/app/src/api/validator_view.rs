use crate::json::{value, Json};
use crate::types::validator::Validator;

pub fn detail(validator: &Validator) -> Json {
    let mut out = Json::obj();
    out.set("id", value::s(&validator.id));
    out.set("network_id", value::s(&validator.network_id));
    out.set("owner_id", value::s(&validator.owner_id));
    out.set("name", value::s(&validator.name));
    out.set("stake", value::n(validator.stake as i64));
    out.set("effective_power", value::n(validator.effective_power as i64));
    out.set("status", value::s(validator.status.as_str()));
    out.set("attested", value::b(validator.attested));
    out.set("created_at", value::n(validator.created_at as i64));
    out
}

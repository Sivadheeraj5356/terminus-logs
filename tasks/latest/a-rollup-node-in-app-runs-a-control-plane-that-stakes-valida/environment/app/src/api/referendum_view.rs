use crate::json::{value, Json};
use crate::types::governance::Referendum;

pub fn detail(referendum: &Referendum) -> Json {
    let mut out = Json::obj();
    out.set("id", value::s(&referendum.id));
    out.set("network_id", value::s(&referendum.network_id));
    out.set("owner_id", value::s(&referendum.owner_id));
    out.set("title", value::s(&referendum.title));
    out.set("visibility", value::s(referendum.visibility.as_str()));
    out.set("created_at", value::n(referendum.created_at as i64));
    out
}

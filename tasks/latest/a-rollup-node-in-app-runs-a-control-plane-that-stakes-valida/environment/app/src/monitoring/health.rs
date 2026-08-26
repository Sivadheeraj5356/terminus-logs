use crate::json::{value, Json};

pub fn health() -> Json {
    let mut out = Json::obj();
    out.set("status", value::s("ok"));
    out.set("service", value::s("keystone"));
    out
}

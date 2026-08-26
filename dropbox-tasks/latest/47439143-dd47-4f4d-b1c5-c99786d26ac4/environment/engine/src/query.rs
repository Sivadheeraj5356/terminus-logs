//! A single authorization query. Frozen evidence.

use crate::ip::parse_ip;
use crate::json::Json;

pub struct Query {
    pub id: String,
    pub domain: String,
    pub ip: Option<u32>,
}

impl Query {
    pub fn from_json(j: &Json) -> Query {
        Query {
            id: j.get("id").map(|v| v.s().to_string()).unwrap_or_default(),
            domain: j.get("domain").map(|v| v.s().to_string()).unwrap_or_default(),
            ip: j.get("ip").and_then(|v| parse_ip(v.s())),
        }
    }
}

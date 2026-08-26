use crate::json::{value, Json};

#[derive(Clone)]
pub struct AuditEvent {
    pub timestamp: u64,
    pub identity: String,
    pub client_addr: String,
    pub operation: String,
    pub target: String,
    pub result: String,
    pub detail: Json,
}

impl AuditEvent {
    pub fn to_json(&self, signature: &str) -> Json {
        Json::from_pairs(vec![
            ("timestamp", value::n(self.timestamp as i64)),
            ("identity", value::s(&self.identity)),
            ("client_addr", value::s(&self.client_addr)),
            ("operation", value::s(&self.operation)),
            ("target", value::s(&self.target)),
            ("result", value::s(&self.result)),
            ("detail", self.detail.clone()),
            ("signature", value::s(signature)),
        ])
    }
}

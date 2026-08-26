use super::audit_event::AuditEvent;
use super::event_sanitizer;
use crate::config::secrets::Secrets;
use crate::json::ser;
use std::fs::OpenOptions;
use std::io::Write;
use std::sync::Mutex;

pub struct AuditLog {
    path: String,
    secrets: Secrets,
    records: Mutex<Vec<AuditEvent>>,
}

impl AuditLog {
    pub fn new(path: &str, secrets: Secrets) -> AuditLog {
        AuditLog {
            path: path.to_string(),
            secrets,
            records: Mutex::new(Vec::new()),
        }
    }

    pub fn record(&self, mut event: AuditEvent) {
        event_sanitizer::sanitize(&mut event.detail);
        let payload = format!(
            "{}|{}|{}|{}",
            event.timestamp, event.identity, event.operation, event.target
        );
        let signature = self.secrets.sign(&payload);
        let line = ser::to_string(&event.to_json(&signature));
        let mut records = self.records.lock().unwrap();
        if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(&self.path) {
            let _ = writeln!(file, "{}", line);
        }
        records.push(event);
    }

    pub fn recent(&self, limit: usize) -> Vec<AuditEvent> {
        let records = self.records.lock().unwrap();
        let start = records.len().saturating_sub(limit);
        records[start..].to_vec()
    }
}

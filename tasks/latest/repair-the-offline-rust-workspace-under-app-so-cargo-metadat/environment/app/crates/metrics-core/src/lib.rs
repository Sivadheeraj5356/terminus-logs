use metrics_macros::RecordMetric;
use serde::{Deserialize, Serialize};

pub const HEALTH_TOKEN: &str = "metrics-factory-ok";

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq, RecordMetric)]
pub struct MetricRecord {
    pub service: String,
    pub latency_ms: u32,
}

pub fn summarize(records: &[MetricRecord]) -> (u32, Vec<String>) {
    let total: u32 = records.iter().map(|r| r.latency_ms).sum();
    let mut services: Vec<String> = records.iter().map(|r| r.service.clone()).collect();
    services.sort_by(|a, b| b.cmp(a));
    (total, services)
}

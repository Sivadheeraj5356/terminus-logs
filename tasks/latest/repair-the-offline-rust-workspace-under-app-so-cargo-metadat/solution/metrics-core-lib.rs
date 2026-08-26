use metrics_macros::RecordMetric;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const HEALTH_TOKEN: &str = "metrics-factory-ok";

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq, RecordMetric)]
pub struct MetricRecord {
    pub service: String,
    pub latency_ms: u32,
}

pub fn summarize(records: &[MetricRecord]) -> (u32, Vec<String>) {
    let total: u32 = records.iter().map(|r| r.latency_ms).sum();
    let mut services: Vec<String> = records.iter().map(|r| r.service.clone()).collect();
    services.sort();
    services.dedup();
    (total, services)
}

pub fn service_totals(records: &[MetricRecord]) -> BTreeMap<String, u32> {
    let mut totals = BTreeMap::new();
    for record in records {
        *totals.entry(record.service.clone()).or_insert(0) += record.latency_ms;
    }
    totals
}

pub fn latency_bounds(records: &[MetricRecord]) -> (u32, u32) {
    let mut min = u32::MAX;
    let mut max = 0u32;
    for record in records {
        min = min.min(record.latency_ms);
        max = max.max(record.latency_ms);
    }
    (min, max)
}

pub mod checksums;
pub mod stream_adapter;
pub mod telemetry;

pub mod generated;

pub fn pack_records(records: &[telemetry::TelemetryRecord]) -> Vec<u8> {
    let mut out = Vec::new();
    for record in records {
        out.extend_from_slice(&record.sensor_id.to_le_bytes());
        out.extend_from_slice(&record.value.to_le_bytes());
        out.push(record.flags);
    }
    out
}

pub fn binding_summary() -> String {
    format!(
        "{}:{}:{}",
        generated::BINDING_TOOL,
        generated::STREAM_INTERFACE,
        generated::WORLD
    )
}

#[cfg(test)]
mod tests {
    use super::{binding_summary, pack_records};
    use crate::telemetry::TelemetryRecord;

    #[test]
    fn pack_records_is_stable() {
        let records = [
            TelemetryRecord::new(7, 11, 1),
            TelemetryRecord::new(9, -3, 4),
        ];
        assert_eq!(pack_records(&records).len(), 18);
    }

    #[test]
    fn generated_bindings_name_preview2_streams() {
        assert!(binding_summary().contains("wasi:io/streams"));
    }
}

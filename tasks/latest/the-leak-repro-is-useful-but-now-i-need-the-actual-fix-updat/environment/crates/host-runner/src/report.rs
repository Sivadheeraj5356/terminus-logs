use crate::cleanup::CleanupMode;
use crate::resource_table::ResourceTable;
use crate::stream_driver::RunResult;

#[derive(Clone, Debug)]
pub struct Report {
    mode: &'static str,
    run_count: usize,
    opened_descriptors: usize,
    dropped_descriptors: usize,
    leaked_descriptors: usize,
    fault_count: usize,
    output_sha256: String,
    observed_events: Vec<&'static str>,
}

impl Report {
    pub fn from_run(mode: CleanupMode, table: &ResourceTable, result: RunResult) -> Self {
        Self {
            mode: mode.as_report_mode(),
            run_count: result.run_count,
            opened_descriptors: table.opened(),
            dropped_descriptors: table.dropped(),
            leaked_descriptors: table.leaked(),
            fault_count: result.fault_count,
            output_sha256: result.output_sha256,
            observed_events: result.observed_events,
        }
    }

    pub fn to_json(&self) -> String {
        let events = self
            .observed_events
            .iter()
            .map(|event| format!("\"{event}\""))
            .collect::<Vec<_>>()
            .join(", ");
        format!(
            "{{\n  \"mode\": \"{}\",\n  \"run_count\": {},\n  \"opened_descriptors\": {},\n  \"dropped_descriptors\": {},\n  \"leaked_descriptors\": {},\n  \"fault_count\": {},\n  \"output_sha256\": \"{}\",\n  \"observed_events\": [{}]\n}}\n",
            self.mode,
            self.run_count,
            self.opened_descriptors,
            self.dropped_descriptors,
            self.leaked_descriptors,
            self.fault_count,
            self.output_sha256,
            events
        )
    }
}

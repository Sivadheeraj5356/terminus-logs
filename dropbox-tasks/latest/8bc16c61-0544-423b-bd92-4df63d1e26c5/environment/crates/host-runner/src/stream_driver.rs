use crate::cleanup::{handle_wasi_error, CleanupMode};
use crate::errors::StreamError;
use crate::fault_plan::FaultPlan;
use crate::resource_table::ResourceTable;
use crate::telemetry::{fixture_paths, read_fixture};
use edge_worker::checksums::fnv1a_hex;
use edge_worker::stream_adapter::pack_bytes;
use std::path::Path;

#[derive(Clone, Debug)]
pub struct RunResult {
    pub run_count: usize,
    pub fault_count: usize,
    pub output_sha256: String,
    pub observed_events: Vec<&'static str>,
}

pub fn run_streams(
    fixtures: &Path,
    fault_plan: &FaultPlan,
    table: &mut ResourceTable,
    mode: CleanupMode,
) -> Result<RunResult, String> {
    let paths = fixture_paths(fixtures)?;
    let mut output = Vec::new();
    let mut fault_count = 0usize;
    let mut observed_events = Vec::new();
    let mut read_index = 0usize;

    for _round in 0..16 {
        for path in &paths {
            read_index += 1;
            let descriptor = table.open_stream();
            match read_one(path, descriptor, read_index, fault_plan, table) {
                Ok(bytes) => {
                    output.extend_from_slice(&pack_bytes(&bytes));
                    table.close_stream(descriptor);
                }
                Err(error) => {
                    fault_count += 1;
                    observed_events.push(error.event);
                    handle_wasi_error(table, &error, mode);
                    output.extend_from_slice(&pack_bytes(&read_fixture(path)?));
                }
            }
        }
    }

    observed_events.sort_unstable();
    observed_events.dedup();

    Ok(RunResult {
        run_count: read_index,
        fault_count,
        output_sha256: fnv1a_hex(&output),
        observed_events,
    })
}

fn read_one(
    path: &Path,
    descriptor: u32,
    read_index: usize,
    fault_plan: &FaultPlan,
    table: &mut ResourceTable,
) -> Result<Vec<u8>, StreamError> {
    if fault_plan.should_fault(read_index) {
        let error = StreamError::transient_read_lag(descriptor);
        table.park_error(error.clone());
        return Err(error);
    }
    read_fixture(path).map_err(|_| StreamError::transient_read_lag(descriptor))
}

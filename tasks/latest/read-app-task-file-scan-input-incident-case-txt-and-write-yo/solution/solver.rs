include!("./solver_core.rs");

use std::path::PathBuf;

fn main() {
    let case_path = PathBuf::from("/app/task_file/scan_input/incident_case.txt");
    let output_path = PathBuf::from("/app/task_file/output/containment_schedule.json");
    let json = solve_to_json(&case_path);
    std::fs::write(output_path, format!("{json}\n")).expect("write containment_schedule.json");
}

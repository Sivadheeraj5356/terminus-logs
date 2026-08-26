include!("./solver_core.rs");

use std::path::PathBuf;

fn main() {
    let case_path = std::env::args()
        .nth(1)
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("/app/task_file/scan_input/incident_case.txt"));
    println!("{}", solve_to_json(&case_path));
}


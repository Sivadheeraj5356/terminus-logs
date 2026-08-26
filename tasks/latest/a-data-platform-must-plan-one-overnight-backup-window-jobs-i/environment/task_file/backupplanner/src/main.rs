mod loader;
mod planner;
mod types;
mod writer;

use std::path::Path;

fn main() {
    let input_dir = Path::new("/app/task_file/input_data");
    let output_dir = Path::new("/app/task_file/output_data");
    std::fs::create_dir_all(output_dir).expect("create output_data");

    let jobs = loader::load_jobs(&input_dir.join("jobs.jsonl"));
    let config = loader::load_config(&input_dir.join("config.json"));
    let plan = planner::build(&jobs, &config);
    writer::write_plan(&output_dir.join("plan.json"), &plan);
    println!("planned {} of {} jobs", plan.assignments.len(), jobs.len());
}

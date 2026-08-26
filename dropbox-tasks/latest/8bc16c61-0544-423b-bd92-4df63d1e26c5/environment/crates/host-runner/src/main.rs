use host_runner::args::Args;
use host_runner::cleanup::CleanupMode;
use host_runner::component::validate_component;
use host_runner::fault_plan::FaultPlan;
use host_runner::report::Report;
use host_runner::resource_table::ResourceTable;
use host_runner::stream_driver::run_streams;
use std::fs;

fn main() {
    let args = Args::parse().unwrap_or_else(|err| {
        eprintln!("{err}");
        std::process::exit(2);
    });
    let mode = CleanupMode::parse(&args.mode).unwrap_or_else(|err| {
        eprintln!("{err}");
        std::process::exit(2);
    });

    validate_component(&args.component).unwrap_or_else(|err| {
        eprintln!("{err}");
        std::process::exit(3);
    });

    let mut table = ResourceTable::new();
    let result = run_streams(&args.fixtures, &FaultPlan::transient(), &mut table, mode)
        .unwrap_or_else(|err| {
            eprintln!("{err}");
            std::process::exit(4);
        });
    let report = Report::from_run(mode, &table, result);
    if let Some(parent) = args.report.parent() {
        fs::create_dir_all(parent).expect("create report parent");
    }
    fs::write(&args.report, report.to_json()).expect("write report");
}

use std::env;
use std::process;

use ambergate_assay_ledger::cli;
use ambergate_assay_ledger::pipeline;

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let mode = cli::parse_mode(&args);
    let code = match mode {
        cli::Mode::Version => {
            print!("assay-ledger 1.0.0\n");
            0
        }
        cli::Mode::Export => match pipeline::run_export() {
            Ok(()) => 0,
            Err(pipeline::PipelineError::MissingSnapshot) => 2,
            Err(_) => 2,
        },
        cli::Mode::Analyze => match pipeline::run_analyze_publish() {
            Ok(()) => 0,
            Err(_) => 2,
        },
        cli::Mode::CheckCoin(id) => match pipeline::run_check_coin(&id) {
            Ok(()) => 0,
            Err(_) => 2,
        },
    };
    process::exit(code);
}

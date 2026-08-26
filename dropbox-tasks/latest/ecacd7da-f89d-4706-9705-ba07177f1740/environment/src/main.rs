mod staged_run;
mod publication;
mod cycle_rules;
mod journal_lanes;
mod lane_exercise;
mod cmpr;
mod mass;
mod normal_run;
mod operator_view;
mod recover_run;
mod recovery;
mod replay;
mod report;
mod seat_gate;
mod session;
mod shift_table;
mod yard_index;
mod journal;
mod ledger;
mod state_digest;

use std::env;
use std::process;

fn main() {
    if let Err(err) = run() {
        eprintln!("compactor_seat error: {err}");
        process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        return Err(
            "usage: compactor_seat --seat <events> ... | --probe-shift-table | --seat-recover <events> ..."
                .into(),
        );
    }
    match args[1].as_str() {
        "--probe-shift-table" => lane_exercise::run_probe(),
        "--seat" => session::run_seat(&args),
        "--seat-recover" => session::run_recover_seat(&args),
        other => Err(format!("unknown mode: {other}")),
    }
}

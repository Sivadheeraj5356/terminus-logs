mod cli;

use std::fs;
use std::path::PathBuf;

use clap::Parser;
use hospital_analytics::beds;
use hospital_analytics::parser::{self, event_merge};
use hospital_analytics::reports;
use hospital_analytics::state::{BedInfo, FacilityState};
use hospital_analytics::validator;

fn main() {
    if let Err(err) = run(cli::Args::parse()) {
        eprintln!("error: {err}");
        std::process::exit(1);
    }
}

fn run(args: cli::Args) -> Result<(), String> {
    let mut state = FacilityState::default();
    load_beds(&mut state, &args.input_dir)?;
    beds::load_ward_capacity(&mut state, &args.input_dir)?;

    let raw = parser::csv_reader::load_all_events(&args.input_dir)?;
    let events = event_merge::merge_events(raw);
    let as_of = parser::csv_reader::load_as_of(&args.input_dir)?;

    for event in &events {
        validator::process_event(&mut state, event);
    }

    let report = reports::build_report(&state, &as_of);
    if let Some(parent) = args.output.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("create output dir: {e}"))?;
    }
    let json = serde_json::to_string_pretty(&report).map_err(|e| format!("serialize: {e}"))?;
    fs::write(&args.output, json).map_err(|e| format!("write output: {e}"))?;
    Ok(())
}

fn load_beds(state: &mut FacilityState, input_dir: &PathBuf) -> Result<(), String> {
    for (bed_id, ward, is_icu, maintenance) in parser::csv_reader::load_beds(input_dir)? {
        state.beds.insert(
            bed_id.clone(),
            BedInfo {
                bed_id,
                ward,
                is_icu,
                maintenance,
            },
        );
    }
    Ok(())
}

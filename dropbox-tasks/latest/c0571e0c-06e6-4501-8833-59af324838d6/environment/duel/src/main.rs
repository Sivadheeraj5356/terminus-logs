use std::env;
use std::fs;
use std::path::{Path, PathBuf};

use sess::{drive_online, run_host};
use serde::{Deserialize, Serialize};

const TAPES_DIR: &str = "/app/environment/tapes";

#[derive(Deserialize)]
struct Tape {
    tape_id: String,
    delay: usize,
    inputs: Vec<[u8; 2]>,
}

#[derive(Serialize)]
struct Row {
    tape_id: String,
    delay: usize,
    ticks: usize,
    host_digest: String,
    pred_digest: String,
    confirmed_digest: String,
    rollbacks: u32,
    converged: bool,
    final_hp: [u8; 2],
}

#[derive(Serialize)]
struct Report {
    rows: Vec<Row>,
}

fn eval(tape: &Tape) -> Row {
    let inputs: Vec<(u8, u8)> = tape.inputs.iter().map(|p| (p[0], p[1])).collect();
    let host = run_host(&inputs);
    let client = drive_online(&inputs, tape.delay);
    Row {
        tape_id: tape.tape_id.clone(),
        delay: tape.delay,
        ticks: inputs.len(),
        host_digest: host.trajectory_digest.clone(),
        pred_digest: client.pred_digest.clone(),
        confirmed_digest: client.confirmed_digest.clone(),
        rollbacks: client.rollbacks,
        converged: client.confirmed_digest == host.trajectory_digest,
        final_hp: [client.final_state.p0.hp, client.final_state.p1.hp],
    }
}

fn load_tape(path: &Path) -> Tape {
    let raw = fs::read_to_string(path).expect("read tape");
    serde_json::from_str(&raw).expect("parse tape")
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut tape_file: Option<PathBuf> = None;
    let mut out = PathBuf::from("/app/output/duel_report.json");
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--tape-file" => {
                i += 1;
                tape_file = Some(PathBuf::from(&args[i]));
            }
            "--out" => {
                i += 1;
                out = PathBuf::from(&args[i]);
            }
            _ => {}
        }
        i += 1;
    }

    if let Some(tf) = tape_file {
        let row = eval(&load_tape(&tf));
        print!("{}", serde_json::to_string(&row).expect("row json"));
        std::process::exit(if row.converged { 0 } else { 1 });
    }

    let dir = Path::new(TAPES_DIR);
    let mut paths: Vec<PathBuf> = fs::read_dir(dir)
        .expect("read tapes dir")
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| p.extension().map(|x| x == "json").unwrap_or(false))
        .collect();
    paths.sort();

    let mut rows = Vec::new();
    let mut all_conv = true;
    for p in &paths {
        let row = eval(&load_tape(p));
        if !row.converged {
            all_conv = false;
        }
        rows.push(row);
    }
    fs::create_dir_all(out.parent().unwrap_or(Path::new("/app/output"))).ok();
    fs::write(&out, serde_json::to_string_pretty(&Report { rows }).expect("report json"))
        .expect("write report");
    std::process::exit(if all_conv { 0 } else { 1 });
}

// Grid revenue-protection audit engine.
//
// `tariff <command> [flags]`
//
//   intake --data <dir> --out <dir>    parse the meter exports, log the evidence
//   draws  --data <dir> --out <dir>    reconstruct the draws, run the fraud detectors
//   settle --data <dir> --out <dir>    settle the expected-revenue baseline, close the case
//   ingest --data <dir> --db <path>    write the case file into SQLite
//   serve  --db <path> --port <n>      serve the case file to the tribunal
//
// /app/spec/FORMATS.md is a format sheet only: corpus paths, the registry field table, the
// packed record layout, the circular grammar and the schema of every report file. It carries
// no rules. The detector rules, the settlement rules and the pricing rules are in the task
// prompt. A worked corpus sits in /app/data/example.
use std::process::exit;

fn main() {
    let argv: Vec<String> = std::env::args().skip(1).collect();
    if argv.is_empty() {
        eprintln!("usage: tariff <command> [flags]");
        exit(2);
    }
    match argv[0].as_str() {
        "intake" | "draws" | "settle" | "ingest" | "serve" => {
            eprintln!("{}: not implemented", argv[0]);
        }
        other => {
            eprintln!("unknown command: {}", other);
            exit(2);
        }
    }
}

mod epoch;
mod fence;
mod gaps;
mod merger;
mod ordering;
mod overlap;
mod parser;
mod report;
mod resolve;
mod span;
mod timezone;

use std::process;

use crate::epoch::{duplicate_slot_id, has_epoch_regression};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!("usage: slot-merge <command> <directory>");
        eprintln!("commands:");
        eprintln!("  merge   <dir>   coalesce overlapping booking slots");
        eprintln!("  gaps    <dir>   uncovered gaps between merged intervals");
        eprintln!("  report  <dir>   per-resource summary table");
        eprintln!("  stats   <dir>   file and record counts");
        eprintln!("  check   <dir>   detect duplicate slot ids and epoch regressions");
        process::exit(1);
    }

    let command = &args[1];
    if args.len() < 3 {
        eprintln!("usage: slot-merge {} <directory>", command);
        process::exit(1);
    }
    let dir = &args[2];

    match command.as_str() {
        "merge" => match merger::merge_directory(dir) {
            Ok(rows) => {
                for r in &rows {
                    let line = serde_json::json!({
                        "resource": r.resource,
                        "start_ms": r.start_ms,
                        "end_ms": r.end_ms,
                        "holder": r.holder,
                    });
                    println!("{}", line);
                }
            }
            Err(e) if e == "no slots" => {
                eprintln!("no slots");
                process::exit(3);
            }
            Err(e) if e.contains("invalid json") => {
                eprintln!("{}", e);
                process::exit(2);
            }
            Err(e) => {
                eprintln!("error: {}", e);
                process::exit(1);
            }
        },
        "gaps" => match gaps::gap_lines(dir) {
            Ok(lines) => {
                for line in lines {
                    println!("{}", line);
                }
            }
            Err(e) if e == "no slots" => {
                eprintln!("no slots");
                process::exit(3);
            }
            Err(e) if e.contains("invalid json") => {
                eprintln!("{}", e);
                process::exit(2);
            }
            Err(e) => {
                eprintln!("error: {}", e);
                process::exit(1);
            }
        },
        "report" => match report::report_lines(dir) {
            Ok(lines) => {
                for line in lines {
                    println!("{}", line);
                }
            }
            Err(e) if e == "no slots" => {
                eprintln!("no slots");
                process::exit(3);
            }
            Err(e) if e.contains("invalid json") => {
                eprintln!("{}", e);
                process::exit(2);
            }
            Err(e) => {
                eprintln!("error: {}", e);
                process::exit(1);
            }
        },
        "stats" => match merger::count_records(dir) {
            Ok((files, records)) => {
                println!(
                    "{}",
                    serde_json::json!({"files": files, "records": records})
                );
            }
            Err(e) if e == "no slots" => {
                eprintln!("no slots");
                process::exit(3);
            }
            Err(e) if e.contains("invalid json") => {
                eprintln!("{}", e);
                process::exit(2);
            }
            Err(e) => {
                eprintln!("error: {}", e);
                process::exit(1);
            }
        },
        "check" => match crate::parser::load_all(dir) {
            Ok(rows) => {
                if duplicate_slot_id(&rows) {
                    eprintln!("duplicate slot id");
                    process::exit(2);
                }
                if has_epoch_regression(dir).unwrap_or(false) {
                    eprintln!("epoch regression");
                    process::exit(2);
                }
                println!("ok");
            }
            Err(e) if e == "no slots" => {
                eprintln!("no slots");
                process::exit(3);
            }
            Err(e) => {
                eprintln!("error: {}", e);
                process::exit(1);
            }
        },
        _ => {
            eprintln!("unknown command: {}", command);
            process::exit(1);
        }
    }
}

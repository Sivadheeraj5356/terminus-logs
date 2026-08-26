//! Resolve and print the release plan.
//!
//! Usage:
//!   planctl resolve --root <dir>     print the resolved plan as JSON
//!   planctl features --root <dir>    print space-separated cargo features

use std::path::PathBuf;
use std::process::exit;

fn arg_value(args: &[String], flag: &str) -> Option<String> {
    args.iter()
        .position(|a| a == flag)
        .and_then(|i| args.get(i + 1))
        .cloned()
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let command = args.get(1).cloned().unwrap_or_default();
    let root = arg_value(&args, "--root").unwrap_or_else(|| ".".to_string());
    let plan = support::resolve(&PathBuf::from(root));

    match command.as_str() {
        "resolve" => println!("{}", plan.to_json()),
        "features" => println!("{}", plan.features().join(" ")),
        _ => {
            eprintln!("planctl: unknown command {command:?}");
            exit(2);
        }
    }
}

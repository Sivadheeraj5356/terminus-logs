//! Sender Authorization Policy differential analyzer.
//!
//! Reads a case file (JSON) whose path is the single argument and prints one
//! certificate per query. The decision itself lives in `analyze.rs`.

mod analyze;
mod io;
mod json;
mod model;
mod parse;

use std::env;
use std::process;

fn main() {
    let path = match env::args().nth(1) {
        Some(p) => p,
        None => {
            eprintln!("usage: analyzer <case.json>");
            process::exit(2);
        }
    };
    io::run(&path);
}

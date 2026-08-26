mod lexer;
mod ast;
mod parser;
mod nfa;
mod dfa;
mod minimize;
mod scan;
mod cli;

use std::process::exit;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    exit(cli::run(&args));
}

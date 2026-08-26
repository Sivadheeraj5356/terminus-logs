use std::env;
use std::path::PathBuf;
use std::process;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("usage: m6_ctl matrix-all");
        process::exit(2);
    }
    if args[1] != "matrix-all" {
        eprintln!("unknown command: {}", args[1]);
        process::exit(2);
    }
    let root = PathBuf::from("/app");
    if let Err(err) = m6_ctl::run_matrix_all(&root) {
        eprintln!("m6_ctl: {err}");
        process::exit(1);
    }
}

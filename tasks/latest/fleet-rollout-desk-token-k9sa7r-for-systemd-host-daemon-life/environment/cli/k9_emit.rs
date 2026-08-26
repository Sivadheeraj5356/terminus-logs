use k9_desk::pack_emit_gateway;
use std::env;
use std::path::PathBuf;

fn main() {
    let mut out = PathBuf::from("/app/output/k9_trace.json");
    let args: Vec<String> = env::args().collect();
    let mut idx = 1;
    while idx < args.len() {
        if args[idx] == "--out" && idx + 1 < args.len() {
            out = PathBuf::from(&args[idx + 1]);
            idx += 2;
        } else {
            idx += 1;
        }
    }
    if !pack_emit_gateway::emit_report(&out) {
        std::process::exit(1);
    }
}

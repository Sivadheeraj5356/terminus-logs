use std::{env, fs, path::Path};

fn main() {
    let path = env::args().nth(1).unwrap_or_else(|| {
        eprintln!("usage: lora-gate <request-file>");
        std::process::exit(2);
    });
    let req = manifest::load::read(Path::new(&path)).unwrap_or_else(|e| {
        eprintln!("request rejected: {e}");
        std::process::exit(2);
    });
    fs::create_dir_all("/app/output").expect("create output directory");
    if let Err(e) = publish::execute(&req) {
        eprintln!("launch failed: {e}");
        std::process::exit(1);
    }
}

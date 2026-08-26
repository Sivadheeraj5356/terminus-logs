use haar_denoiser::{resolve_paths, run_all, run_decompose, run_export, run_ingest};

fn main() {
    let mut args = std::env::args().skip(1);
    let mode = args.next();
    let result = match mode.as_deref() {
        Some("version") => {
            println!("haar-denoiser 0.1.0");
            Ok(())
        }
        Some("ingest-traces") => resolve_paths().and_then(|p| run_ingest(&p)),
        Some("decompose-threshold") => resolve_paths().and_then(|p| run_decompose(&p)),
        Some("reconstruct-export") => resolve_paths().and_then(|p| run_export(&p)),
        None => resolve_paths().and_then(|p| run_all(&p)),
        Some(other) => Err(format!("unknown mode: {other}")),
    };
    if let Err(e) = result {
        eprintln!("{e}");
        std::process::exit(1);
    }
}

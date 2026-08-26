use yarder::{args::Args, catalog, flow};

fn main() {
    let cfg = match Args::parse() {
        Ok(v) => v,
        Err(e) => {
            eprintln!("{e}");
            std::process::exit(2);
        }
    };
    let result = if cfg.mode == "list" {
        catalog::list_names(&cfg)
    } else {
        flow::phase_a(&cfg)
    };
    if let Err(e) = result {
        eprintln!("{e}");
        std::process::exit(3);
    }
}

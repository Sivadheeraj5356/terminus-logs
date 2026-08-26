/// xscope — legacy record bundle checker CLI.
///
/// Usage:
///   xscope --all-samples --bundle-out <path>
///   xscope --group <name> --bundle-out <path>
///
/// The checker loads fixtures from /app/environment/fixtures/, runs the
/// decoder pipeline, and writes the validated bundle to <path>.

mod engine;
mod report;
mod report_stub;

use clap::Parser;
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(name = "xscope", about = "Legacy record bundle checker")]
struct Args {
    /// Process all sample groups.
    #[arg(long)]
    all_samples: bool,

    /// Process a single named group (e.g. set_a).
    #[arg(long)]
    group: Option<String>,

    /// Output path for the generated bundle JSON.
    #[arg(long)]
    bundle_out: PathBuf,

    /// Fixtures directory (default: /app/environment/fixtures).
    #[arg(long, default_value = "/app/environment/fixtures")]
    fixtures_dir: PathBuf,
}

fn main() {
    let args = Args::parse();

    if !args.all_samples && args.group.is_none() {
        eprintln!("error: specify --all-samples or --group <name>");
        std::process::exit(2);
    }

    let bundle = if args.all_samples {
        engine::run_all_groups(&args.fixtures_dir)
    } else {
        let group_name = args.group.as_deref().unwrap();
        let raw_path = args
            .fixtures_dir
            .join("raw")
            .join(format!("{}.bin", group_name));
        let txt_path = args
            .fixtures_dir
            .join("text")
            .join(format!("{}.txt", group_name));

        let grp = engine::process_group(group_name, &raw_path, &txt_path);
        report::Bundle {
            groups: vec![grp],
            artifacts: vec![],
        }
    };

    match report::write_bundle(&bundle, &args.bundle_out) {
        Ok(()) => {
            println!(
                "bundle written to {}",
                args.bundle_out.display()
            );
        }
        Err(e) => {
            eprintln!("error: {}", e);
            std::process::exit(1);
        }
    }
}

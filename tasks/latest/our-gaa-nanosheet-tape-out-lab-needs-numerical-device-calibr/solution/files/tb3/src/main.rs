use clap::{Parser, Subcommand};
use tb3::foundry_card::{build_validation, write_spice, write_validation};
use tb3::nsheet_physics::load_bounds;
use tb3::nsheet_physics::run_fit as fit_pipeline;
use tb3::lab_corpus::load_bundle;
use tb3::calib_seal::{build_rollup, build_tapeout, read_rollup, read_tapeout, write_rollup, write_tapeout};
use tb3::{
    resolve_bounds_path, DEFAULT_BOUNDS, DEFAULT_DATA, DEFAULT_ROLLUP, DEFAULT_SPICE,
    DEFAULT_TAPEOUT, DEFAULT_VALIDATION,
};

#[derive(Parser)]
#[command(name = "gaa-extract")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    Characterize {
        #[arg(long, default_value = DEFAULT_DATA)]
        data_dir: String,
        #[arg(long = "tapeout", alias = "tapeout", default_value = DEFAULT_TAPEOUT)]
        tapeout: String,
        #[arg(long, default_value = DEFAULT_ROLLUP)]
        rollup: String,
    },
    ModelFit {
        #[arg(long = "tapeout", alias = "tapeout", default_value = DEFAULT_TAPEOUT)]
        tapeout: String,
        #[arg(long, default_value = DEFAULT_ROLLUP)]
        rollup: String,
        #[arg(long, default_value = DEFAULT_BOUNDS)]
        bounds: String,
        #[arg(long, default_value = DEFAULT_SPICE)]
        spice: String,
        #[arg(long, default_value = DEFAULT_VALIDATION)]
        validation: String,
    },
    Run {
        #[arg(long, default_value = DEFAULT_DATA)]
        data_dir: String,
        #[arg(long = "tapeout", alias = "tapeout", default_value = DEFAULT_TAPEOUT)]
        tapeout: String,
        #[arg(long, default_value = DEFAULT_ROLLUP)]
        rollup: String,
        #[arg(long, default_value = DEFAULT_BOUNDS)]
        bounds: String,
        #[arg(long, default_value = DEFAULT_SPICE)]
        spice: String,
        #[arg(long, default_value = DEFAULT_VALIDATION)]
        validation: String,
    },
}

fn run_characterize(data_dir: &str, tapeout_path: &str, rollup_path: &str) -> Result<(), String> {
    let (geometries, iv_points, cv_points, contacts, ref_temp) = load_bundle(data_dir)?;
    let tapeout = build_tapeout(geometries, iv_points, cv_points, contacts, ref_temp);
    let rollup = build_rollup(&tapeout);
    write_tapeout(std::path::Path::new(tapeout_path), &tapeout)?;
    write_rollup(std::path::Path::new(rollup_path), &rollup)
}

fn run_model_fit(
    tapeout_path: &str,
    rollup_path: &str,
    bounds_path: &str,
    spice_path: &str,
    validation_path: &str,
) -> Result<(), String> {
    let tapeout = read_tapeout(std::path::Path::new(tapeout_path))?;
    let rollup = read_rollup(std::path::Path::new(rollup_path))?;
    if rollup.measure_digest != tapeout.measure_digest {
        return Err("rollup measure_digest does not match tapeout".to_string());
    }
    let bounds_file = resolve_bounds_path(bounds_path)?;
    let bounds = load_bounds(&bounds_file)?;
    let (fitted, metrics, convergence) = fit_pipeline(&tapeout, &rollup, &bounds)?;
    write_spice(std::path::Path::new(spice_path), &tapeout, &fitted)?;
    let validation = build_validation(&tapeout, &rollup, &fitted, &metrics, convergence);
    write_validation(std::path::Path::new(validation_path), &validation)
}

fn main() {
    let cli = Cli::parse();
    let result = match cli.command {
        Commands::Characterize {
            data_dir,
            tapeout,
            rollup,
        } => run_characterize(&data_dir, &tapeout, &rollup),
        Commands::ModelFit {
            tapeout,
            rollup,
            bounds,
            spice,
            validation,
        } => run_model_fit(&tapeout, &rollup, &bounds, &spice, &validation),
        Commands::Run {
            data_dir,
            tapeout,
            rollup,
            bounds,
            spice,
            validation,
        } => run_characterize(&data_dir, &tapeout, &rollup).and_then(|_| {
            run_model_fit(&tapeout, &rollup, &bounds, &spice, &validation)
        }),
    };
    if let Err(err) = result {
        eprintln!("gaa-extract error: {err}");
        std::process::exit(1);
    }
}

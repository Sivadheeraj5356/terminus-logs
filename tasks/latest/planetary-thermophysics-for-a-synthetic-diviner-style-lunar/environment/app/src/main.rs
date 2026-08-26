mod cli;
mod data;
mod error;
mod inversion;
mod model;
mod nonlinear;
mod radiometry;
mod report;
mod thermal;

use report::remove_stale_outputs;

fn main() {
    let args = match cli::parse_args() {
        Ok(args) => args,
        Err(message) => {
            eprintln!("{message}");
            std::process::exit(2);
        }
    };

    remove_stale_outputs(&args.output);

    // Reference incomplete physics modules so the starter builds with the
    // full module layout before the thermal / radiometry / inversion work.
    let _ = (
        thermal::solve_cases,
        nonlinear::solve_nonlinear_step,
        radiometry::band_radiance,
        radiometry::brightness_temperature,
        inversion::solve_fits,
        report::write_report_atomic,
        model::SolverReport {
            time_step_rows: Vec::new(),
            temperature_rows: Vec::new(),
            surface_flux_rows: Vec::new(),
            radiometer_rows: Vec::new(),
            inverse_fit_rows: Vec::new(),
            solver_diagnostics: Vec::new(),
            summary: model::ReportSummary {
                case_count: 0,
                observation_count: 0,
                radiometer_row_count: 0,
                inverse_fit_count: 0,
                converged_inverse_fit_count: 0,
                minimum_surface_temperature_k: 0.0,
                maximum_surface_temperature_k: 0.0,
                maximum_brightness_temperature_k: 0.0,
                minimum_inversion_objective: 0.0,
                maximum_absolute_energy_residual_j_m2: 0.0,
            },
        },
    );

    match data::load_solver_data(&args.data_dir) {
        Ok(_solver_data) => {
            eprintln!("thermal model, radiometry, and inversion are not implemented");
        }
        Err(err) => {
            eprintln!("failed to load solver data: {err}");
        }
    }
    std::process::exit(2);
}

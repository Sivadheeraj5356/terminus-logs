pub mod snapshot;
pub mod staging;

use crate::cli::IngestArgs;
use crate::config::load_policy;

pub fn run_ingest(args: &IngestArgs) -> Result<(), i32> {
    let _policy = load_policy(&args.policy).map_err(|code| {
        eprintln!("{code}");
        1
    })?;
    let bundle_path = snapshot::resolve_bundle_path(&args.bundle);
    let artifact = staging::load_bundle(&bundle_path).map_err(|code| {
        eprintln!("{code}");
        1
    })?;
    staging::write_staging(&args.staging, &artifact)?;
    snapshot::persist_snapshot(&artifact)?;
    Ok(())
}

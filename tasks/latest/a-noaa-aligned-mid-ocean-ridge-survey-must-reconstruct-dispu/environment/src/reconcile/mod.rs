pub mod merge;

use crate::cli::ReconcileArgs;
use crate::ingest::staging;
use crate::precedence::resolver;

pub fn run_reconcile(args: &ReconcileArgs) -> Result<(), i32> {
    let resolved = resolver::load_resolved(&args.resolved).map_err(|code| {
        eprintln!("{code}");
        1
    })?;
    let staging_path = std::path::Path::new("/app/state")
        .join(format!("{}-dives.json", resolved.expedition_id));
    let staging = staging::load_staging(&staging_path).map_err(|code| {
        eprintln!("{code}");
        1
    })?;
    let reconciled = merge::reconcile(&resolved, &staging);
    merge::write_reconciled(&args.output, &reconciled)?;
    Ok(())
}

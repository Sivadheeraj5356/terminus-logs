pub mod atlas;

use crate::cli::ExportArgs;
use crate::config::load_policy;
use crate::precedence::resolver;
use crate::reconcile::merge;

pub fn run_export(args: &ExportArgs) -> Result<(), i32> {
    let _policy = load_policy(&args.policy).map_err(|code| {
        eprintln!("{code}");
        1
    })?;
    let reconciled = merge::load_reconciled(&args.observations).map_err(|code| {
        eprintln!("{code}");
        1
    })?;
    let resolved_path = std::path::Path::new("/app/state")
        .join(format!("{}-resolved.json", reconciled.expedition_id));
    let resolved = resolver::load_resolved(&resolved_path).map_err(|code| {
        eprintln!("{code}");
        1
    })?;
    atlas::write_atlas(&args.atlas, &reconciled, &resolved.reports)?;
    Ok(())
}

pub mod resolver;

use crate::cli::ResolveArgs;
use crate::ingest::staging;

pub fn run_resolve(args: &ResolveArgs) -> Result<(), i32> {
    let staging = staging::load_staging(&args.staging).map_err(|code| {
        eprintln!("{code}");
        1
    })?;
    let resolved = resolver::resolve(&staging);
    resolver::write_resolved(&args.output, &resolved)?;
    resolver::persist_resolved(&resolved)?;
    Ok(())
}

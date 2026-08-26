#[path = "../../w4n/reconcile_c.rs"]
mod reconcile_c;
#[path = "../../w4n/walk_n.rs"]
mod walk_n;

pub use reconcile_c::reconcile_c;
pub use walk_n::walk_n;

use crate::r9m;

/// Bundle fetch + manifest serialization for the entrypoint.
pub fn emit_bundle(port: u16, graph_path: &str) -> Result<String, String> {
    let (rooms, moves, endpoint, status) = reconcile_c(port, graph_path)?;
    r9m::seal(port, graph_path, &rooms, &moves, &endpoint, status)
}

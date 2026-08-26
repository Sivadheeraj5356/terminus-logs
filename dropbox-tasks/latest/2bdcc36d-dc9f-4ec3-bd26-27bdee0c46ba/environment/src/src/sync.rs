use crate::merkle::{MerkleDag, MerkleExport};
use crate::operation::Operation;
use crate::vector_clock::VectorClock;

pub const SYNC_NOT_IMPLEMENTED: &str = "sync protocol not implemented";

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SyncError {
    MergeFailed(String),
}

impl std::fmt::Display for SyncError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SyncError::MergeFailed(msg) => write!(f, "sync merge failed: {msg}"),
        }
    }
}

impl std::error::Error for SyncError {}

pub fn anti_entropy(local: &mut MerkleDag, remote: &MerkleDag) -> Result<usize, SyncError> {
    let paths = local
        .diff_paths(remote)
        .map_err(|e| SyncError::MergeFailed(e.to_string()))?;
    if paths.is_empty() {
        return Ok(0);
    }
    let exports = collect_exports(remote, &paths)?;
    apply_exports(local, &exports)?;
    Ok(exports.len())
}

pub fn collect_exports(dag: &MerkleDag, paths: &[String]) -> Result<Vec<MerkleExport>, SyncError> {
    let mut out = Vec::with_capacity(paths.len());
    for path in paths {
        match dag.export_node(path) {
            Ok(export) => out.push(export),
            Err(_) => continue,
        }
    }
    Ok(out)
}

pub fn apply_exports(dag: &mut MerkleDag, exports: &[MerkleExport]) -> Result<(), SyncError> {
    for export in exports {
        dag.import_node(export.clone())
            .map_err(|e| SyncError::MergeFailed(e.to_string()))?;
    }
    Ok(())
}

pub fn merge_operation_log(
    local_ops: &mut Vec<(Operation, VectorClock)>,
    remote_ops: &[(Operation, VectorClock)],
) -> Result<(), SyncError> {
    let mut seen = local_ops
        .iter()
        .map(|(op, _)| op.id())
        .collect::<std::collections::HashSet<_>>();
    for (op, clock) in remote_ops {
        if seen.insert(op.id()) {
            local_ops.push((op.clone(), clock.clone()));
        }
    }
    local_ops.sort_by_key(|(op, _)| op.id().counter);
    Ok(())
}

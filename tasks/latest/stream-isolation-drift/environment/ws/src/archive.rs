use std::path::Path;

/// Read-only archive compaction unrelated to live runs.
pub fn compact_archive(root: &Path) -> usize {
    root.read_dir()
        .map(|entries| entries.count())
        .unwrap_or(0)
}

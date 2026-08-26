use crate::journal::{load_entries, SeatEntry};

pub fn ordered_entries(journal_path: &str) -> Result<Vec<SeatEntry>, String> {
    let entries = load_entries(journal_path)?;
    let mut seen = std::collections::HashSet::new();
    let mut kept = Vec::new();
    for entry in entries {
        if seen.insert(entry.seq) {
            kept.push(entry);
        }
    }
    kept.sort_by_key(|e| e.seq);
    Ok(kept)
}

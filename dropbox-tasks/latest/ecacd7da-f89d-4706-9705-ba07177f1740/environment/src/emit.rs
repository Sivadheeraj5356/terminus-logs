use crate::span::seated_memory_bytes;
use crate::store::Store;
use serde_json::{json, Value};

pub fn build_report(
    store: &Store,
    rollback_performed: bool,
    fences_placed: u32,
    _seated_rows: u32,
) -> Value {
    json!({
        "slices_seated": store.record_count(),
        "fences_placed": fences_placed,
        "memory_seated": seated_memory_bytes(store),
        "rollback_performed": rollback_performed,
        "ready": !rollback_performed,
    })
}

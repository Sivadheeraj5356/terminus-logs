use crate::store::Store;

pub fn seated_memory_bytes(store: &Store) -> u64 {
    store
        .records_snapshot()
        .values()
        .map(|rec| rec.memory_bytes)
        .sum()
}

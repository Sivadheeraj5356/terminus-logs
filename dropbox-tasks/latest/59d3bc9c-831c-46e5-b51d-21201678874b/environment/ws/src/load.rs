use super::{read_manifest, Store, VaultMark};

pub fn load_mark(store: &Store) -> VaultMark {
    read_manifest(store).unwrap_or(VaultMark {
        last_generation: 0,
        last_pass: 0,
        open_count: 0,
    })
}

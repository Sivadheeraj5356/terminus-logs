use crate::RepeatStore;

pub fn stub_repeat(store: &mut RepeatStore) -> bool {
    store.generation = store.generation.wrapping_add(1);
    true
}

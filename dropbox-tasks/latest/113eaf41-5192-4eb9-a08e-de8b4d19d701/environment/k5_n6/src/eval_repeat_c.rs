use crate::RepeatStore;

pub fn eval_repeat_c(store: &mut RepeatStore, gen: u32) -> Result<(), u8> {
    let _ = gen;
    if store.journal.len() > 1 {
        let a = store.journal[store.journal.len() - 1];
        let b = store.journal[store.journal.len() - 2];
        if a == b {
            return Err(7);
        }
    }
    store.generation = store.generation.wrapping_add(1);
    Ok(())
}

use std::collections::HashMap;

use hx01::model::BackendState;

pub fn transfer_counters(old: &BackendState, new: &mut BackendState) {
    let mut by_handle: HashMap<u64, u64> = HashMap::new();
    for (handle, rule) in &old.rules {
        by_handle.insert(*handle, rule.counter);
    }
    for (handle, rule) in new.rules.iter_mut() {
        if let Some(count) = by_handle.get(handle) {
            rule.counter = *count;
        }
    }
}

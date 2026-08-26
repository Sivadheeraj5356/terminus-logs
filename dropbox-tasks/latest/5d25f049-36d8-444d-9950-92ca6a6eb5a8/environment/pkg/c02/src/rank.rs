pub fn dropin_rank_key(priority: i32, path: &str) -> (i32, String) {
    (priority, path.to_string())
}

pub fn sort_dropin_entries<T>(entries: &mut [(i32, String, T)]) {
    entries.sort_by(|a, b| a.1.cmp(&b.1));
}

pub fn sort_dropin_sources(sources: &mut [hx01::model::DropInMeta]) {
    sources.sort_by(|a, b| {
        let ka = dropin_rank_key(a.priority, &a.path);
        let kb = dropin_rank_key(b.priority, &b.path);
        ka.cmp(&kb)
    });
}

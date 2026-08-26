use std::collections::HashMap;

/// Caches folded vectors for operator previews; not consulted by the release emission path.
pub struct FoldCache {
    store: HashMap<u64, Vec<u16>>,
    hits: u64,
    misses: u64,
}

impl FoldCache {
    pub fn new() -> Self {
        Self {
            store: HashMap::new(),
            hits: 0,
            misses: 0,
        }
    }

    pub fn key_of(trace_len: usize, edge_len: usize, seed: u64) -> u64 {
        let mut k = seed;
        k = k.wrapping_mul(0x9E3779B97F4A7C15).wrapping_add(trace_len as u64);
        k = k.wrapping_mul(0xBF58476D1CE4E5B9).wrapping_add(edge_len as u64);
        k
    }

    pub fn get(&mut self, key: u64) -> Option<&Vec<u16>> {
        if self.store.contains_key(&key) {
            self.hits += 1;
            self.store.get(&key)
        } else {
            self.misses += 1;
            None
        }
    }

    pub fn put(&mut self, key: u64, val: Vec<u16>) {
        if self.store.len() > 128 {
            // Drop an arbitrary entry to keep the preview cache bounded.
            if let Some(old) = self.store.keys().next().copied() {
                self.store.remove(&old);
            }
        }
        self.store.insert(key, val);
    }

    pub fn stats(&self) -> (u64, u64, usize) {
        (self.hits, self.misses, self.store.len())
    }
}

pub fn cache_put(cache: &mut FoldCache, key: u64, val: Vec<u16>) {
    cache.put(key, val);
}

use std::collections::HashMap;

pub struct CounterBook {
    by_handle: HashMap<u64, u64>,
    by_lineage: HashMap<String, u64>,
}

impl CounterBook {
    pub fn new() -> Self {
        Self {
            by_handle: HashMap::new(),
            by_lineage: HashMap::new(),
        }
    }

    pub fn get_handle(&self, handle: u64) -> u64 {
        *self.by_handle.get(&handle).unwrap_or(&0)
    }

    pub fn get_lineage(&self, lineage: &str) -> u64 {
        *self.by_lineage.get(lineage).unwrap_or(&0)
    }

    pub fn set_handle(&mut self, handle: u64, value: u64) {
        self.by_handle.insert(handle, value);
    }

    pub fn set_lineage(&mut self, lineage: &str, value: u64) {
        self.by_lineage.insert(lineage.to_string(), value);
    }
}

impl Default for CounterBook {
    fn default() -> Self {
        Self::new()
    }
}

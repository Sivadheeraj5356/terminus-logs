#[derive(Debug, Default, Clone)]
pub struct Pager {
    pub page_count: u32,
    pub map: Vec<(u32, u32)>,
    pub free_stack: Vec<u32>,
}

impl Pager {
    pub fn allocate(&mut self, logical: u32) -> u32 {
        if let Some(pos) = self.map.iter().position(|(l, _)| *l == logical) {
            return self.map[pos].1;
        }
        let physical = if let Some(p) = self.free_stack.pop() {
            p
        } else {
            let p = self.page_count;
            self.page_count += 1;
            p
        };
        self.map.push((logical, physical));
        physical
    }

    pub fn release(&mut self, physical: u32) {
        if let Some(idx) = self.map.iter().position(|(_, p)| *p == physical) {
            self.map.remove(idx);
            self.free_stack.push(physical);
        }
    }

    pub fn release_logical(&mut self, logical: u32) {
        if let Some(idx) = self.map.iter().position(|(l, _)| *l == logical) {
            let physical = self.map[idx].1;
            self.map.remove(idx);
            self.free_stack.push(physical);
        }
    }

    pub fn free_ratio(&self) -> f64 {
        let denom = self.page_count.max(1) as f64;
        self.free_stack.len() as f64 / denom
    }

    pub fn maybe_compact(&mut self, threshold: f64) -> bool {
        if self.free_ratio() <= threshold {
            return false;
        }
        // renumber densely by ascending prior logical order
        self.map.sort_by_key(|(l, _)| *l);
        for (i, entry) in self.map.iter_mut().enumerate() {
            entry.1 = i as u32;
        }
        self.page_count = self.map.len() as u32;
        self.free_stack.clear();
        true
    }

    pub fn physical_ids_sorted(&self) -> Vec<u32> {
        let mut v: Vec<u32> = self.map.iter().map(|(_, p)| *p).collect();
        v.sort_unstable();
        v
    }
}

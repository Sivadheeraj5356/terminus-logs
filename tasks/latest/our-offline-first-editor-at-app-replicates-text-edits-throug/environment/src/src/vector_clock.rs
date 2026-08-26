use std::collections::HashMap;

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct VectorClock {
    clocks: HashMap<u32, u64>,
}

impl VectorClock {
    pub fn new() -> Self {
        Self {
            clocks: HashMap::new(),
        }
    }

    pub fn increment(&mut self, replica: u32) {
        *self.clocks.entry(replica).or_insert(0) += 1;
    }

    pub fn merge(&mut self, other: &VectorClock) {
        for (replica, tick) in &other.clocks {
            let entry = self.clocks.entry(*replica).or_insert(0);
            if *tick > *entry {
                *entry = *tick;
            }
        }
    }

    pub fn get(&self, replica: u32) -> u64 {
        self.clocks.get(&replica).copied().unwrap_or(0)
    }

    pub fn canonical_bytes(&self) -> Vec<u8> {
        let mut pairs: Vec<(u32, u64)> = self.clocks.iter().map(|(&r, &t)| (r, t)).collect();
        pairs.sort_by_key(|(r, _)| *r);
        let mut out = Vec::new();
        for (replica, tick) in pairs {
            out.extend_from_slice(&replica.to_le_bytes());
            out.extend_from_slice(&tick.to_le_bytes());
        }
        out
    }
}

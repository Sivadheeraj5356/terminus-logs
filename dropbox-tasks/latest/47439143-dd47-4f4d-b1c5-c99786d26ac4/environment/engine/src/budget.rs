//! Evaluation limits. Frozen evidence.

pub const LOOKUP_LIMIT: u32 = 8;

/// How deep one query may follow policies into other domains. This bounds a
/// zone whose policies delegate in a cycle.
pub const MAX_DELEGATION: u32 = 32;

pub struct Budget {
    used: u32,
}

impl Budget {
    pub fn new() -> Budget {
        Budget { used: 0 }
    }

    /// Charge one unit for a term that performs a zone lookup. Returns Err once
    /// the budget is exhausted.
    pub fn charge(&mut self) -> Result<(), ()> {
        self.used += 1;
        if self.used > LOOKUP_LIMIT {
            Err(())
        } else {
            Ok(())
        }
    }
}

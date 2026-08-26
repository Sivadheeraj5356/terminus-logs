#[derive(Clone, Debug)]
pub struct FaultPlan {
    every: usize,
}

impl FaultPlan {
    pub fn transient() -> Self {
        Self { every: 5 }
    }

    pub fn should_fault(&self, read_index: usize) -> bool {
        read_index % self.every == self.every
    }
}

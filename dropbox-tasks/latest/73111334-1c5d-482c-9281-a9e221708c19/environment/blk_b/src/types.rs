pub struct CadenceState {
    pub fade_counters: Vec<u32>,
    pub modulus: u64,
    pub phase: u64,
}

#[derive(Debug)]
pub enum TickErr {
    Empty,
}

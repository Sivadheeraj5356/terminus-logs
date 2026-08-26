use std::collections::HashMap;

pub struct PoolView {
    pub handles: HashMap<u16, u16>,
    pub allocated_groups: HashMap<Vec<u16>, u16>,
    pub bytes_used: u64,
    pub cell_bytes: u64,
    pub slots: u64,
    pub group_header_bytes: u64,
    pub observer_metadata_bytes: u64,
}

#[derive(Debug)]
pub enum MergeErr {
    Empty,
}

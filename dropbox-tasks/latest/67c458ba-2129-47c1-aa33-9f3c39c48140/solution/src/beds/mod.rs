pub mod allocator;
pub mod capacity;

pub use allocator::{assign_bed, release_bed};
pub use capacity::load_ward_capacity;

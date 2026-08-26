//! Shared release-support library: profile reading and plan resolution.

pub mod conf;
pub mod plan;

pub use plan::{resolve, Plan};

//! Workspace crate driving `/app/output/` artifacts via `harness::drive`.

pub mod cfg_parse;
pub mod errors;
pub mod harness;
pub mod rotation_spec;
pub mod reload_lane;
pub mod idle;
pub mod logging;
pub mod proto;
#[path = "../cm/mod.rs"]
pub mod seg;
pub mod ceil_cell;
#[path = "../ax/mod.rs"]
pub mod hp;
pub mod types;

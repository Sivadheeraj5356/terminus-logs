//! BSIM-CMG style inspection helpers available to lab notebooks.
//! These helpers are not part of the foundry SPICE card emission path.

mod wrap;

pub use wrap::{inspect_drive_current, inspect_param_lines};


// Legacy record decoder library.
//
// Module layout:
//   types    — shared record and state types
//   model    — canonical-view projection helpers
//   a1       — binary record reader (module A)
//   b1       — compatibility trace builder (module B)
//   c1       — malformed-input classifier (module C)
//   compat   — compatibility shim coordinating b1 and c1
//   *_stub   — alternate decoy modules not on the live path

pub mod types;
pub mod model;

pub mod a1;
pub mod a1_stub;

pub mod b1;
pub mod b1_stub;

pub mod c1;
pub mod c1_stub;

pub mod compat;
pub mod compat_stub;

pub mod model_stub;

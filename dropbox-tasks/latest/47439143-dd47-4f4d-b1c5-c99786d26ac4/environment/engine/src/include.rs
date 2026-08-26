//! Mapping a nested `include` evaluation result to a match decision. Frozen
//! evidence.

use crate::result::SapResult;

/// An `include` matches when the nested policy authorizes the sender.
pub fn include_matches(nested: SapResult) -> bool {
    matches!(nested, SapResult::Pass)
}

//! Oracle bracket module — implements `golden_bracket` per
//! docs/contracts/bracket.md.

use crate::fibonacci::fibonacci;

pub fn golden_bracket(indices: &[u32]) -> (u64, u64) {
    match indices.iter().max() {
        Some(&max_k) => (fibonacci(max_k + 1), fibonacci(max_k)),
        None => (0, 0),
    }
}

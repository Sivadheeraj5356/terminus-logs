//! Bounded single-line diagnostics without host leakage.
use std::io::{self, Write};

pub fn emit_error(code: i32, msg: &str) {
    let cleaned: String = msg
        .chars()
        .map(|c| if c.is_control() { ' ' } else { c })
        .take(200)
        .collect();
    let _ = writeln!(io::stderr(), "unitgraph error {}: {}", code, cleaned);
}

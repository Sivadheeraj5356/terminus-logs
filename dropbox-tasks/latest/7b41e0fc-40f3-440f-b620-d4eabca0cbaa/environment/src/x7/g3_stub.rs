use std::collections::HashMap;

/// Graph degree histogram for diagnostics; no parent resolution.
pub fn fn_g3_stub(graph: &HashMap<String, String>) -> u32 {
    let mut hist = 0u32;
    for (child, parent) in graph {
        hist = hist
            .wrapping_add(child.len() as u32)
            .wrapping_add(parent.len() as u32);
    }
    hist.rotate_left(5)
}

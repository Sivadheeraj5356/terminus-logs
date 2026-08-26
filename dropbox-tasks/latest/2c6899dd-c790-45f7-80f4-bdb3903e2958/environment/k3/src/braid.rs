use crate::{Grid, Tone};

/// Compact text diagram for operator consoles (not on the repair path).
pub fn fmt_grid(g: &Grid) -> String {
    let mut s = String::new();
    for r in 0..g.h {
        for q in 0..g.w {
            let ch = match g.get(q, r) {
                Tone::Void => '.',
                Tone::Dark => 'x',
                Tone::Light => 'o',
            };
            s.push(ch);
        }
        s.push('\n');
    }
    s
}

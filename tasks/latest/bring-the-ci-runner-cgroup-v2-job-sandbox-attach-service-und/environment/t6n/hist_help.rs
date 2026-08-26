//! Histogram formatter for support tooling (non-authority).

pub fn fmt_bins(vals: &[u32]) -> String {
    let mut out = String::new();
    for (i, v) in vals.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        out.push_str(&format!("{v}"));
    }
    out
}

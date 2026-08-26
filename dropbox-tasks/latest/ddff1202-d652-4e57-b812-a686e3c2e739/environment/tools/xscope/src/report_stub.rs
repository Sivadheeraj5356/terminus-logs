/// Alternate report helper (not wired into the active output writer).

#[allow(dead_code)]
pub fn format_summary(group: &str, compat: usize, total: usize) -> String {
    format!("{}: {}/{} compatible", group, compat, total)
}

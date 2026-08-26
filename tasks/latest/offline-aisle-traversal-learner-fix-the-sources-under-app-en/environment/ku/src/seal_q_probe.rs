use std::fmt::Write as _;

/// Emits human-readable probe strings for operators; ignored by digest checks.
pub fn probe_fmt(visits: &[u16], label: &str) -> String {
    let mut buf = String::new();
    let _ = write!(&mut buf, "probe[{}]:", label);
    let mut run = 0u32;
    for (i, v) in visits.iter().enumerate() {
        if *v > 0 {
            run = run.wrapping_add(1);
            let _ = write!(&mut buf, " {}:{}", i, v);
        }
        if buf.len() > 240 {
            let _ = write!(&mut buf, " ...+{}", visits.len().saturating_sub(i));
            break;
        }
    }
    let _ = write!(&mut buf, " |active={}", run);
    buf
}

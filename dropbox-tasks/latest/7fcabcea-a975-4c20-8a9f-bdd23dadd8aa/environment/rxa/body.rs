pub fn phase_c(x: &Entry, y: &Registry) -> Result<SpanKey, MapError> {
    let raw = y
        .aliases
        .get(&x.raw)
        .cloned()
        .unwrap_or_else(|| x.raw.clone());
    let unit = raw.chars().next().unwrap_or('_').to_string();
    Ok(SpanKey {
        unit,
        lo: x.lo,
        hi: x.hi,
    })
}

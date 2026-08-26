use std::collections::HashMap;

use crate::corpus::{Kind, Ordinance};
use crate::Result;

#[derive(Clone, Debug)]
pub struct Segment {
    pub start: i64,
    pub end: Option<i64>,
    pub ordinance: String,
    pub stdoff: i32,
}

/// `standard-offset: basis ORD-X` resolves transitively to the literal offset the
/// terminal ordinance of the chain establishes.
pub fn resolve_basis(ords: &[Ordinance]) -> Result<HashMap<String, i32>> {
    let by_id: HashMap<&str, &Ordinance> = ords.iter()
        .filter(|o| o.kind == Kind::Establish)
        .map(|o| (o.oid.as_str(), o))
        .collect();
    let mut out: HashMap<String, i32> = HashMap::new();
    for o in ords.iter().filter(|o| o.kind == Kind::Establish) {
        let mut seen: Vec<&str> = Vec::new();
        let mut cur = o.oid.as_str();
        let value = loop {
            if let Some(v) = out.get(cur) {
                break *v;
            }
            if seen.contains(&cur) {
                return Err(format!("basis cycle at {cur}").into());
            }
            seen.push(cur);
            let node = by_id.get(cur).ok_or_else(|| format!("unknown basis {cur}"))?;
            match (&node.basis, node.std_offset) {
                (Some(next), _) => cur = next.as_str(),
                (None, Some(v)) => break v,
                (None, None) => return Err(format!("{cur} has no offset").into()),
            }
        };
        for oid in seen {
            out.insert(oid.to_string(), value);
        }
    }
    Ok(out)
}

/// Governing intervals. The offset table was keyed by the date a change took effect,
/// so the latest row at or before an instant decides the offset there.
pub fn segments_from(
    ords: &[Ordinance],
    eff: &HashMap<String, i64>,
    seq: &HashMap<String, i64>,
    stdoffs: &HashMap<String, i32>,
) -> Result<Vec<Segment>> {
    let mut windows: Vec<(i64, Option<i64>, (i64, i64), &str)> = Vec::new();
    for o in ords.iter().filter(|o| o.kind == Kind::Establish) {
        let start = eff[&o.oid];
        windows.push((start, None, (start, seq[&o.oid]), o.oid.as_str()));
    }
    if windows.is_empty() {
        return Err("no effective ordinances".into());
    }

    let mut bounds: Vec<i64> = windows.iter().map(|w| w.0).collect();
    bounds.sort_unstable();
    bounds.dedup();

    let mut pieces: Vec<(i64, Option<i64>, &str)> = Vec::new();
    for (i, &b) in bounds.iter().enumerate() {
        let next = bounds.get(i + 1).copied();
        let gov = windows.iter()
            .filter(|w| w.0 <= b && w.1.map(|e| b < e).unwrap_or(true))
            .max_by_key(|w| w.2);
        if let Some(w) = gov {
            pieces.push((b, next, w.3));
        }
    }

    let mut merged: Vec<Segment> = Vec::new();
    for (start, end, gov) in pieces {
        match merged.last_mut() {
            Some(last) if last.ordinance == gov && last.end == Some(start) => last.end = end,
            _ => merged.push(Segment {
                start,
                end,
                ordinance: gov.to_string(),
                stdoff: stdoffs[gov],
            }),
        }
    }
    Ok(merged)
}

pub fn governing_at(segments: &[Segment], t: i64) -> Option<&Segment> {
    if segments.is_empty() || t < segments[0].start {
        return None;
    }
    let mut lo = 0usize;
    let mut hi = segments.len() - 1;
    while lo < hi {
        let mid = (lo + hi + 1) / 2;
        if segments[mid].start <= t { lo = mid } else { hi = mid - 1 }
    }
    Some(&segments[lo])
}

use std::collections::{BTreeMap, HashSet};

use crate::epoch;
use crate::parser;
use crate::span;

struct Agg {
    slots: u64,
    holders: HashSet<String>,
    min_start: u64,
    max_end: u64,
    empty: bool,
}

pub fn report_lines(dir: &str) -> Result<Vec<String>, String> {
    let all = parser::load_all(dir)?;
    let current = epoch::max_epoch_rows(&all);

    let mut by_resource: BTreeMap<String, Agg> = BTreeMap::new();
    for row in current {
        let key = parser::canonical_resource(&row.resource);
        let entry = by_resource.entry(key).or_insert(Agg {
            slots: 0,
            holders: HashSet::new(),
            min_start: row.start_ms,
            max_end: row.end_ms,
            empty: true,
        });
        entry.slots += 1;
        entry.holders.insert(row.holder.clone());
        if entry.empty {
            entry.min_start = row.start_ms;
            entry.max_end = row.end_ms;
            entry.empty = false;
        } else {
            if row.start_ms < entry.min_start {
                entry.min_start = row.start_ms;
            }
            if row.end_ms > entry.max_end {
                entry.max_end = row.end_ms;
            }
        }
    }

    let mut rows: Vec<(String, u64, u64, u64)> = by_resource
        .into_iter()
        .map(|(resource, agg)| {
            let span = span::resource_span(agg.min_start, agg.max_end, agg.empty);
            (resource, agg.slots, agg.holders.len() as u64, span)
        })
        .collect();
    rows.sort_by(|a, b| a.3.cmp(&b.3).then_with(|| a.0.cmp(&b.0)));

    let total_slots: u64 = rows.iter().map(|r| r.1).sum();
    let total_holders: u64 = rows.iter().map(|r| r.2).sum();
    let total_span: u64 = rows.iter().map(|r| r.3).sum();

    let col_width = |header: &str, total: &str, cells: &dyn Fn() -> Vec<usize>| -> usize {
        let mut w = header.len().max(total.len());
        for c in cells() {
            w = w.max(c);
        }
        w
    };

    let rw = col_width("RESOURCE", "TOTAL", &|| rows.iter().map(|r| r.0.len()).collect());
    let sw = col_width("SLOTS", &total_slots.to_string(), &|| {
        rows.iter().map(|r| r.1.to_string().len()).collect()
    });
    let hw = col_width("HOLDERS", &total_holders.to_string(), &|| {
        rows.iter().map(|r| r.2.to_string().len()).collect()
    });
    let pw = col_width("SPAN", &total_span.to_string(), &|| {
        rows.iter().map(|r| r.3.to_string().len()).collect()
    });

    let lpad = |s: &str, w: usize| format!("{}{}", s, " ".repeat(w - s.len()));

    let mut out = Vec::new();
    out.push(format!(
        "{}  {}  {}  {}",
        lpad("RESOURCE", rw),
        lpad("SLOTS", sw),
        lpad("HOLDERS", hw),
        lpad("SPAN", pw)
    ));
    let sep = format!(
        "{}  {}  {}  {}",
        "-".repeat(rw),
        "-".repeat(sw),
        "-".repeat(hw),
        "-".repeat(pw)
    );
    out.push(sep.clone());
    for (resource, slots, holders, span) in &rows {
        out.push(format!(
            "{}  {}  {}  {}",
            lpad(resource, rw),
            lpad(&slots.to_string(), sw),
            lpad(&holders.to_string(), hw),
            lpad(&span.to_string(), pw)
        ));
    }
    out.push(sep);
    out.push(format!(
        "{}  {}  {}  {}",
        lpad("TOTAL", rw),
        lpad(&total_slots.to_string(), sw),
        lpad(&total_holders.to_string(), hw),
        lpad(&total_span.to_string(), pw)
    ));
    Ok(out)
}

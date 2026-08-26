#!/bin/bash
# Oracle solution: restore the five parts of tzforge that still followed the retiring
# offset table, then rebuild.
set -euo pipefail

cd /app

cat > /app/src/precedence.rs <<'TZFORGE_EOF'
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

/// Governing intervals. At an instant the governing ordinance is the establishing one
/// with the greatest enactment sequence among those in force there.
pub fn segments_from(
    ords: &[Ordinance],
    eff: &HashMap<String, i64>,
    seq: &HashMap<String, i64>,
    stdoffs: &HashMap<String, i32>,
) -> Result<Vec<Segment>> {
    let mut repeal_at: HashMap<&str, i64> = HashMap::new();
    for o in ords.iter().filter(|o| o.kind == Kind::Repeal) {
        let target = o.repeals.as_deref().unwrap();
        if !eff.contains_key(target) {
            return Err(format!("{} repeals unknown {target}", o.oid).into());
        }
        let at = eff[&o.oid];
        repeal_at.entry(target).and_modify(|e| *e = (*e).min(at)).or_insert(at);
    }

    let mut windows: Vec<(i64, Option<i64>, i64, &str)> = Vec::new();
    for o in ords.iter().filter(|o| o.kind == Kind::Establish) {
        let start = eff[&o.oid];
        let end = repeal_at.get(o.oid.as_str()).copied();
        if end.map(|e| e > start).unwrap_or(true) {
            windows.push((start, end, seq[&o.oid], o.oid.as_str()));
        }
    }
    if windows.is_empty() {
        return Err("no effective ordinances".into());
    }

    let mut bounds: Vec<i64> = windows.iter().map(|w| w.0).collect();
    bounds.extend(windows.iter().filter_map(|w| w.1));
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
TZFORGE_EOF

cat > /app/src/anchor.rs <<'TZFORGE_EOF'
use std::collections::HashMap;

use crate::calendar::recur::to_ut;
use crate::corpus::Ordinance;
use crate::precedence::Segment;
use crate::timeline::state_of;

/// The UT instant an ordinance takes effect. A wall or standard anchor is resolved
/// against the offset and save established by the ordinance governing the instant
/// immediately before it, never against the incoming ordinance's own offset.
pub fn effective_instant(
    o: &Ordinance,
    seg: Option<&Segment>,
    by_id: &HashMap<String, &Ordinance>,
    stdoffs: &HashMap<String, i32>,
    meridian: i32,
    guess: i64,
) -> i64 {
    let (sb_std, sb_save) = match seg {
        None => (meridian, 0),
        Some(s) => {
            let g = by_id[&s.ordinance];
            let std = stdoffs[&g.oid];
            (std, state_of(g, std, guess - 1).0)
        }
    };
    to_ut(o.eff_civil, o.eff_anchor, sb_std, sb_save)
}
TZFORGE_EOF

cat > /app/src/calendar/civil.rs <<'TZFORGE_EOF'
pub const MONTHS: [&str; 12] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
pub const WEEKDAYS: [&str; 7] = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const MDAYS: [i64; 12] = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

pub fn is_leap(y: i64) -> bool {
    y % 4 == 0 && (y % 100 != 0 || y % 400 == 0)
}

pub fn days_in_month(y: i64, m: i64) -> i64 {
    if m == 2 && is_leap(y) { 29 } else { MDAYS[(m - 1) as usize] }
}

fn fdiv(a: i64, b: i64) -> i64 {
    let q = a / b;
    if (a % b != 0) && ((a < 0) != (b < 0)) { q - 1 } else { q }
}

pub fn days_from_civil(y: i64, m: i64, d: i64) -> i64 {
    let yy = y - if m <= 2 { 1 } else { 0 };
    let era = fdiv(if yy >= 0 { yy } else { yy - 399 }, 400);
    let yoe = yy - era * 400;
    let mp = m + if m > 2 { -3 } else { 9 };
    let doy = (153 * mp + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146097 + doe - 719468
}

pub fn civil_from_days(z: i64) -> (i64, i64, i64) {
    let z = z + 719468;
    let era = fdiv(if z >= 0 { z } else { z - 146096 }, 146097);
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let yy = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = mp + if mp < 10 { 3 } else { -9 };
    (yy + if m <= 2 { 1 } else { 0 }, m, d)
}

/// 0 = Sunday. `%` truncates towards zero in Rust, so pre-1970 days need rem_euclid.
pub fn weekday_from_days(z: i64) -> i64 {
    (z + 4).rem_euclid(7)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DayKind { Last, Ge, Le, Fixed }

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct DaySpec {
    pub kind: DayKind,
    pub weekday: i64,
    pub day: i64,
}

pub fn resolve_day(y: i64, m: i64, spec: DaySpec) -> i64 {
    match spec.kind {
        DayKind::Fixed => spec.day,
        DayKind::Last => {
            let last = days_in_month(y, m);
            let z = days_from_civil(y, m, last);
            last - (weekday_from_days(z) - spec.weekday).rem_euclid(7)
        }
        DayKind::Ge => {
            let z = days_from_civil(y, m, spec.day);
            spec.day + (spec.weekday - weekday_from_days(z)).rem_euclid(7)
        }
        DayKind::Le => {
            let z = days_from_civil(y, m, spec.day);
            spec.day - (weekday_from_days(z) - spec.weekday).rem_euclid(7)
        }
    }
}

/// Naive local seconds for a recurrence in year `y`. `tod` may exceed 86400.
pub fn civil_seconds(y: i64, m: i64, spec: DaySpec, tod: i64) -> i64 {
    let d = resolve_day(y, m, spec);
    days_from_civil(y, m, d) * 86400 + tod
}

pub fn year_of(ut: i64) -> i64 {
    civil_from_days(fdiv(ut, 86400)).0
}
TZFORGE_EOF

cat > /app/src/emit/tzif.rs <<'TZFORGE_EOF'
use sha2::{Digest, Sha256};

use crate::timeline::{type_index, Zone, INT32_MAX, INT32_MIN};

const MAGIC: &[u8; 4] = b"TZif";

fn designations(zone: &Zone) -> (Vec<u8>, Vec<u8>) {
    let mut buf = Vec::new();
    let mut offs = Vec::new();
    for t in &zone.types {
        offs.push(buf.len() as u8);
        buf.extend_from_slice(t.abbrev.as_bytes());
        buf.push(0);
    }
    (buf, offs)
}

fn header(timecnt: u32, typecnt: u32, charcnt: u32) -> Vec<u8> {
    let mut out = Vec::with_capacity(44);
    out.extend_from_slice(MAGIC);
    out.push(b'2');
    out.extend_from_slice(&[0u8; 15]);
    for v in [typecnt, typecnt, 0, timecnt, typecnt, charcnt] {
        out.extend_from_slice(&v.to_be_bytes());
    }
    out
}

fn block(zone: &Zone, transitions: &[&crate::timeline::Transition], wide: bool,
         chars: &[u8], offs: &[u8]) -> Vec<u8> {
    let index = type_index(zone);
    let mut out = Vec::new();
    for tr in transitions {
        if wide {
            out.extend_from_slice(&tr.ut.to_be_bytes());
        } else {
            out.extend_from_slice(&(tr.ut as i32).to_be_bytes());
        }
    }
    for tr in transitions {
        out.push(index[&(tr.utoff, tr.isdst, tr.abbrev.clone())]);
    }
    for (i, t) in zone.types.iter().enumerate() {
        out.extend_from_slice(&t.utoff.to_be_bytes());
        out.push(t.isdst);
        out.push(offs[i]);
    }
    out.extend_from_slice(chars);
    for t in &zone.types {
        out.push(t.isstd);
    }
    for t in &zone.types {
        out.push(t.isut);
    }
    out
}

pub fn serialize(zone: &Zone) -> Vec<u8> {
    let (chars, offs) = designations(zone);
    let typecnt = zone.types.len() as u32;
    let charcnt = chars.len() as u32;

    let all: Vec<&crate::timeline::Transition> = zone.transitions.iter().collect();
    let v1: Vec<&crate::timeline::Transition> = zone.transitions.iter()
        .filter(|t| (INT32_MIN..=INT32_MAX).contains(&t.ut))
        .collect();

    let mut out = Vec::new();
    out.extend(header(v1.len() as u32, typecnt, charcnt));
    out.extend(block(zone, &v1, false, &chars, &offs));
    out.extend(header(all.len() as u32, typecnt, charcnt));
    out.extend(block(zone, &all, true, &chars, &offs));
    out.push(b'\n');
    out.extend_from_slice(zone.footer.as_bytes());
    out.push(b'\n');
    out
}

pub fn sha256_hex(data: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(data);
    h.finalize().iter().map(|b| format!("{b:02x}")).collect()
}
TZFORGE_EOF

cat > /app/src/emit/posix.rs <<'TZFORGE_EOF'
use crate::calendar::civil::{DayKind, DaySpec};
use crate::calendar::recur::{Anchor, Event};
use crate::corpus::Ordinance;
use crate::timeline::label_for;
use crate::Result;

fn name(abbrev: &str) -> String {
    if abbrev.len() >= 3 && abbrev.chars().all(|c| c.is_ascii_alphabetic()) {
        abbrev.to_string()
    } else {
        format!("<{abbrev}>")
    }
}

/// POSIX offsets are the value added to local time to reach UT: the sign inverts.
pub fn fmt_offset(utoff: i32) -> String {
    fmt_hms(-utoff)
}

pub fn fmt_hms(v: i32) -> String {
    let sign = if v < 0 { "-" } else { "" };
    let a = v.abs();
    let (h, m, s) = (a / 3600, (a % 3600) / 60, a % 60);
    if s != 0 {
        format!("{sign}{h}:{m:02}:{s:02}")
    } else if m != 0 {
        format!("{sign}{h}:{m:02}")
    } else {
        format!("{sign}{h}")
    }
}

fn week_rule(month: i64, spec: DaySpec) -> Result<String> {
    match spec.kind {
        DayKind::Last => Ok(format!("M{}.5.{}", month, spec.weekday)),
        DayKind::Ge if matches!(spec.day, 1 | 8 | 15 | 22) => {
            Ok(format!("M{}.{}.{}", month, (spec.day - 1) / 7 + 1, spec.weekday))
        }
        _ => Err(format!("day specifier {spec:?} is not expressible in a POSIX footer").into()),
    }
}

/// The rule time is the local wall clock in force immediately before the transition.
fn wall_before(ev: &Event, stdoff: i32, save_before: i32) -> i64 {
    match ev.anchor {
        Anchor::Wall => ev.tod,
        Anchor::Standard => ev.tod + save_before as i64,
        Anchor::Universal => ev.tod + stdoff as i64 + save_before as i64,
    }
}

fn rule(ev: &Event, stdoff: i32, save_before: i32) -> Result<String> {
    let mut text = week_rule(ev.month, ev.day)?;
    let wall = wall_before(ev, stdoff, save_before);
    if wall != 7200 {
        text.push('/');
        text.push_str(&fmt_hms(wall as i32));
    }
    Ok(text)
}

pub fn footer_string(o: &Ordinance, stdoff: i32) -> Result<String> {
    let std_label = o.std_label.as_deref().unwrap_or("LMT");
    let obs = match &o.observance {
        None => return Ok(format!("{}{}", name(&label_for(std_label, stdoff)), fmt_offset(stdoff))),
        Some(obs) => obs,
    };

    let save = obs.begin.save;
    let dst_utoff = stdoff + save;
    let mut text = String::new();
    text.push_str(&name(&label_for(std_label, stdoff)));
    text.push_str(&fmt_offset(stdoff));
    text.push_str(&name(&label_for(&obs.begin.label, dst_utoff)));
    if dst_utoff != stdoff + 3600 {
        text.push_str(&fmt_offset(dst_utoff));
    }
    text.push(',');
    text.push_str(&rule(&obs.begin, stdoff, 0)?);
    text.push(',');
    text.push_str(&rule(&obs.end, stdoff, save)?);
    Ok(text)
}
TZFORGE_EOF


cargo build --release --offline
/app/bin/pgstart.sh
/app/target/release/tzforge build

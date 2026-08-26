use std::fs;
use std::path::Path;

use crate::calendar::civil::{days_from_civil, DayKind, DaySpec, MONTHS, WEEKDAYS};
use crate::calendar::recur::{Anchor, Event, Observance};
use crate::Result;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind { Establish, Repeal }

#[derive(Clone, Debug)]
pub struct Ordinance {
    pub oid: String,
    pub zone: String,
    pub kind: Kind,
    pub enacted: i64,
    pub enacted_text: String,
    pub seq: i64,
    pub eff_civil: i64,
    pub eff_anchor: Anchor,
    pub std_offset: Option<i32>,
    pub basis: Option<String>,
    pub std_label: Option<String>,
    pub observance: Option<Observance>,
    pub repeals: Option<String>,
}

pub fn parse_offset(text: &str) -> Result<i32> {
    let bytes = text.as_bytes();
    if bytes.len() < 8 || (bytes[0] != b'+' && bytes[0] != b'-') {
        return Err(format!("bad offset {text:?}").into());
    }
    let parts: Vec<&str> = text[1..].split(':').collect();
    if parts.len() != 3 {
        return Err(format!("bad offset {text:?}").into());
    }
    let h: i32 = parts[0].parse()?;
    let m: i32 = parts[1].parse()?;
    let s: i32 = parts[2].parse()?;
    let v = h * 3600 + m * 60 + s;
    Ok(if bytes[0] == b'-' { -v } else { v })
}

pub fn parse_tod(text: &str) -> Result<i64> {
    let parts: Vec<&str> = text.split(':').collect();
    if parts.len() != 3 {
        return Err(format!("bad time of day {text:?}").into());
    }
    let h: i64 = parts[0].parse()?;
    let m: i64 = parts[1].parse()?;
    let s: i64 = parts[2].parse()?;
    Ok(h * 3600 + m * 60 + s)
}

fn weekday_index(name: &str) -> Result<i64> {
    WEEKDAYS.iter().position(|w| *w == name)
        .map(|i| i as i64)
        .ok_or_else(|| format!("bad weekday {name:?}").into())
}

fn month_index(name: &str) -> Result<i64> {
    MONTHS.iter().position(|w| *w == name)
        .map(|i| i as i64 + 1)
        .ok_or_else(|| format!("bad month {name:?}").into())
}

pub fn parse_dayspec(text: &str) -> Result<DaySpec> {
    if let Some(rest) = text.strip_prefix("last") {
        return Ok(DaySpec { kind: DayKind::Last, weekday: weekday_index(rest)?, day: 0 });
    }
    if let Some(idx) = text.find(">=") {
        return Ok(DaySpec {
            kind: DayKind::Ge,
            weekday: weekday_index(&text[..idx])?,
            day: text[idx + 2..].parse()?,
        });
    }
    if let Some(idx) = text.find("<=") {
        return Ok(DaySpec {
            kind: DayKind::Le,
            weekday: weekday_index(&text[..idx])?,
            day: text[idx + 2..].parse()?,
        });
    }
    if let Some(rest) = text.strip_prefix('d') {
        return Ok(DaySpec { kind: DayKind::Fixed, weekday: 0, day: rest.parse()? });
    }
    Err(format!("bad day specifier {text:?}").into())
}

fn parse_event(text: &str, default_save: i32, default_label: Option<&str>) -> Result<Event> {
    let parts: Vec<&str> = text.split_whitespace().collect();
    if parts.len() < 4 {
        return Err(format!("bad observance line {text:?}").into());
    }
    let month = month_index(parts[0])?;
    let day = parse_dayspec(parts[1])?;
    let tod = parse_tod(parts[2])?;
    let anchor = Anchor::parse(parts[3]).ok_or_else(|| format!("bad anchor {:?}", parts[3]))?;
    let mut save = default_save;
    let mut label = default_label.map(str::to_string);
    let mut i = 4;
    while i < parts.len() {
        match parts[i] {
            "save" => { save = parse_offset(parts[i + 1])?; i += 2; }
            "label" => { label = Some(parts[i + 1].to_string()); i += 2; }
            other => return Err(format!("unknown observance token {other:?}").into()),
        }
    }
    let label = label.ok_or("observance event needs a label")?;
    Ok(Event { month, day, tod, anchor, save, label })
}

fn parse_date(text: &str) -> Result<i64> {
    let p: Vec<&str> = text.split('-').collect();
    if p.len() != 3 {
        return Err(format!("bad date {text:?}").into());
    }
    Ok(days_from_civil(p[0].parse()?, p[1].parse()?, p[2].parse()?))
}

pub fn parse_ordinance(path: &Path) -> Result<Ordinance> {
    let raw = fs::read_to_string(path)?;
    let mut fields: Vec<(String, String)> = Vec::new();
    let mut obs: Vec<(String, String)> = Vec::new();
    let mut in_obs = false;

    for line in raw.lines() {
        if line.trim().is_empty() || line.trim_start().starts_with('#') {
            continue;
        }
        if line.starts_with("  ") {
            if !in_obs {
                return Err("indented line outside observance".into());
            }
            let (k, v) = line.trim().split_once(':').ok_or("bad observance line")?;
            obs.push((k.trim().to_string(), v.trim().to_string()));
            continue;
        }
        in_obs = false;
        let (k, v) = line.split_once(':').ok_or("bad field line")?;
        let (k, v) = (k.trim(), v.trim());
        if k == "observance" {
            in_obs = true;
            continue;
        }
        if fields.iter().any(|(ek, _)| ek == k) {
            return Err(format!("duplicate field {k:?}").into());
        }
        fields.push((k.to_string(), v.to_string()));
    }

    let get = |name: &str| -> Option<&str> {
        fields.iter().find(|(k, _)| k == name).map(|(_, v)| v.as_str())
    };
    let need = |name: &str| -> Result<&str> {
        get(name).ok_or_else(|| format!("missing field {name:?}").into())
    };

    let oid = need("ordinance")?.to_string();
    let seq: i64 = oid.rsplit('-').next().ok_or("bad id")?.parse()?;
    let zone = need("jurisdiction")?.to_string();
    let enacted_text = need("enacted")?.to_string();
    let enacted = parse_date(&enacted_text)?;

    let eff = need("effective")?;
    let (stamp, anchor_text) = eff.split_once(char::is_whitespace).ok_or("bad effective")?;
    let anchor = Anchor::parse(anchor_text.trim())
        .ok_or_else(|| format!("bad effective anchor {anchor_text:?}"))?;
    let (date, time) = stamp.split_once('T').ok_or("bad effective stamp")?;
    let eff_civil = parse_date(date)? * 86400 + parse_tod(time)?;

    if let Some(target) = get("repeals") {
        if get("standard-offset").is_some() || !obs.is_empty() {
            return Err("a repeal ordinance establishes nothing".into());
        }
        return Ok(Ordinance {
            oid, zone, kind: Kind::Repeal, enacted, enacted_text, seq, eff_civil,
            eff_anchor: anchor, std_offset: None, basis: None, std_label: None,
            observance: None, repeals: Some(target.to_string()),
        });
    }

    let so = need("standard-offset")?;
    let (std_offset, basis) = match so.strip_prefix("basis ") {
        Some(b) => (None, Some(b.trim().to_string())),
        None => (Some(parse_offset(so)?), None),
    };
    let std_label = need("standard-label")?.to_string();

    let observance = if obs.is_empty() {
        None
    } else {
        let begin_text = obs.iter().find(|(k, _)| k == "begin").map(|(_, v)| v.as_str())
            .ok_or("observance needs begin")?;
        let end_text = obs.iter().find(|(k, _)| k == "end").map(|(_, v)| v.as_str())
            .ok_or("observance needs end")?;
        Some(Observance {
            begin: parse_event(begin_text, 3600, None)?,
            end: parse_event(end_text, 0, Some(&std_label))?,
        })
    };

    Ok(Ordinance {
        oid, zone, kind: Kind::Establish, enacted, enacted_text, seq, eff_civil,
        eff_anchor: anchor, std_offset, basis, std_label: Some(std_label),
        observance, repeals: None,
    })
}

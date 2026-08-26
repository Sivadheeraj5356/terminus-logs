use crate::calendar::civil::{DayKind, DaySpec};
use crate::calendar::recur::{Anchor, Event};
use crate::corpus::Ordinance;
use crate::timeline::label_for;
use crate::Result;

fn name(abbrev: &str) -> String {
    abbrev.to_string()
}

/// The table's consumers took offsets positive east of the prime meridian.
pub fn fmt_offset(utoff: i32) -> String {
    fmt_hms(utoff)
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

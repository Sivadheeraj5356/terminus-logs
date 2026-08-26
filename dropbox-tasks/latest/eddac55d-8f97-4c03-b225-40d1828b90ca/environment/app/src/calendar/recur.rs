use super::civil::{civil_seconds, DaySpec};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Anchor { Wall, Standard, Universal }

impl Anchor {
    pub fn parse(s: &str) -> Option<Anchor> {
        match s {
            "wall" => Some(Anchor::Wall),
            "standard" => Some(Anchor::Standard),
            "universal" => Some(Anchor::Universal),
            _ => None,
        }
    }
    pub fn as_str(&self) -> &'static str {
        match self {
            Anchor::Wall => "wall",
            Anchor::Standard => "standard",
            Anchor::Universal => "universal",
        }
    }
    pub fn isstd(&self) -> u8 {
        if *self == Anchor::Wall { 0 } else { 1 }
    }
    pub fn isut(&self) -> u8 {
        if *self == Anchor::Universal { 1 } else { 0 }
    }
}

/// A naive local instant becomes UT using the offset and save in force just before it.
pub fn to_ut(civ: i64, anchor: Anchor, stdoff: i32, save_before: i32) -> i64 {
    match anchor {
        Anchor::Universal => civ,
        Anchor::Standard => civ - stdoff as i64,
        Anchor::Wall => civ - stdoff as i64 - save_before as i64,
    }
}

#[derive(Clone, Debug)]
pub struct Event {
    pub month: i64,
    pub day: DaySpec,
    pub tod: i64,
    pub anchor: Anchor,
    pub save: i32,
    pub label: String,
}

#[derive(Clone, Debug)]
pub struct Observance {
    pub begin: Event,
    pub end: Event,
}

impl Observance {
    /// The two recurrence instants of calendar year `y`, each anchored against the
    /// save in force immediately before it.
    pub fn events_for_year(&self, stdoff: i32, y: i64) -> [(i64, i32, &str, Anchor); 2] {
        let b = &self.begin;
        let e = &self.end;
        let cb = civil_seconds(y, b.month, b.day, b.tod);
        let ce = civil_seconds(y, e.month, e.day, e.tod);
        [
            (to_ut(cb, b.anchor, stdoff, 0), b.save, b.label.as_str(), b.anchor),
            (to_ut(ce, e.anchor, stdoff, b.save), e.save, e.label.as_str(), e.anchor),
        ]
    }
}

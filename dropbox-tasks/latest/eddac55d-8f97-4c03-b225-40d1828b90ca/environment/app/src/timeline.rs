use std::collections::HashMap;

use crate::anchor::effective_instant;
use crate::calendar::civil::year_of;
use crate::calendar::recur::{to_ut, Anchor, Observance};
use crate::corpus::{Kind, Ordinance, ZoneMeta};
use crate::emit::posix::footer_string;
use crate::precedence::{governing_at, resolve_basis, segments_from, Segment};
use crate::Result;

pub const HORIZON: i64 = 2145916799; // 2037-12-31T23:59:59Z
pub const INT32_MIN: i64 = i32::MIN as i64;
pub const INT32_MAX: i64 = i32::MAX as i64;

#[derive(Clone, Debug)]
pub struct Transition {
    pub ut: i64,
    pub utoff: i32,
    pub isdst: u8,
    pub abbrev: String,
    pub anchor: Anchor,
    pub ordinance: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Ttype {
    pub utoff: i32,
    pub isdst: u8,
    pub abbrev: String,
    pub isstd: u8,
    pub isut: u8,
}

#[derive(Clone, Debug)]
pub struct ResolvedOrd {
    pub oid: String,
    pub kind: Kind,
    pub enacted_text: String,
    pub enactment_seq: i64,
    pub effective_epoch: i64,
    pub effective_anchor: Anchor,
    pub standard_offset: Option<i32>,
    pub basis: Option<String>,
    pub repeals: Option<String>,
}

pub struct Zone {
    pub name: String,
    pub meridian: i32,
    pub transitions: Vec<Transition>,
    pub segments: Vec<Segment>,
    pub types: Vec<Ttype>,
    pub footer: String,
    pub ordinances: Vec<ResolvedOrd>,
    /// The perpetual rule the footer encodes: what governs past the last transition.
    pub perpetual: Option<Observance>,
    pub perpetual_stdoff: i32,
    pub perpetual_label: String,
    pub perpetual_anchor: Anchor,
}

impl Zone {
    pub fn local_at(&self, t: i64) -> (i32, u8, String) {
        if self.transitions.is_empty() || t < self.transitions[0].ut {
            return (self.meridian, 0, "LMT".to_string());
        }
        if t > self.transitions.last().unwrap().ut {
            let (save, label, _) = state_from(self.perpetual.as_ref(), &self.perpetual_label,
                                              self.perpetual_anchor, self.perpetual_stdoff, t);
            let utoff = self.perpetual_stdoff + save;
            return (utoff, u8::from(save != 0), label_for(&label, utoff));
        }
        let mut lo = 0usize;
        let mut hi = self.transitions.len() - 1;
        while lo < hi {
            let mid = (lo + hi + 1) / 2;
            if self.transitions[mid].ut <= t { lo = mid } else { hi = mid - 1 }
        }
        let tr = &self.transitions[lo];
        (tr.utoff, tr.isdst, tr.abbrev.clone())
    }

    /// The offset in force immediately before each transition.
    pub fn offsets_before(&self) -> Vec<i32> {
        let mut prev = self.meridian;
        let mut out = Vec::with_capacity(self.transitions.len());
        for tr in &self.transitions {
            out.push(prev);
            prev = tr.utoff;
        }
        out
    }
}

pub fn numeric_label(utoff: i32) -> String {
    let sign = if utoff < 0 { '-' } else { '+' };
    let a = utoff.abs();
    let (h, m, s) = (a / 3600, (a % 3600) / 60, a % 60);
    if s != 0 {
        format!("{sign}{h:02}{m:02}{s:02}")
    } else if m != 0 {
        format!("{sign}{h:02}{m:02}")
    } else {
        format!("{sign}{h:02}")
    }
}

pub fn label_for(text: &str, utoff: i32) -> String {
    if text == "numeric" { numeric_label(utoff) } else { text.to_string() }
}

/// The save, label and anchor in force at instant `t`, taking the most recent
/// recurrence at or before `t` — including one from the previous year.
pub fn state_from(obs: Option<&Observance>, std_label: &str, fallback: Anchor,
                  stdoff: i32, t: i64) -> (i32, String, Anchor) {
    let obs = match obs {
        None => return (0, std_label.to_string(), fallback),
        Some(obs) => obs,
    };
    let y = year_of(t);
    let mut best: Option<(i64, i32, String, Anchor)> = None;
    for yy in (y - 2)..=(y + 1) {
        for (ut, save, label, anchor) in obs.events_for_year(stdoff, yy) {
            if ut <= t && best.as_ref().map(|b| ut > b.0).unwrap_or(true) {
                best = Some((ut, save, label.to_string(), anchor));
            }
        }
    }
    let b = best.expect("recurrence recurs indefinitely in both directions");
    (b.1, b.2, b.3)
}

pub fn state_of(o: &Ordinance, stdoff: i32, t: i64) -> (i32, String, Anchor) {
    state_from(o.observance.as_ref(), o.std_label.as_deref().unwrap_or(""),
               o.eff_anchor, stdoff, t)
}

fn zone_types(meridian: i32, transitions: &[Transition]) -> (Vec<Ttype>, HashMap<(i32, u8, String), u8>) {
    let mut types = vec![Ttype {
        utoff: meridian, isdst: 0, abbrev: "LMT".to_string(), isstd: 0, isut: 0,
    }];
    let mut index: HashMap<(i32, u8, String), u8> = HashMap::new();
    index.insert((meridian, 0, "LMT".to_string()), 0);
    for tr in transitions {
        let key = (tr.utoff, tr.isdst, tr.abbrev.clone());
        if !index.contains_key(&key) {
            index.insert(key, types.len() as u8);
            types.push(Ttype {
                utoff: tr.utoff,
                isdst: tr.isdst,
                abbrev: tr.abbrev.clone(),
                isstd: tr.anchor.isstd(),
                isut: tr.anchor.isut(),
            });
        }
    }
    (types, index)
}

pub fn type_index(zone: &Zone) -> HashMap<(i32, u8, String), u8> {
    zone_types(zone.meridian, &zone.transitions).1
}

pub fn build_zone(meta: &ZoneMeta, ords: &[Ordinance]) -> Result<Zone> {
    let stdoffs = resolve_basis(ords)?;
    let by_id: HashMap<String, &Ordinance> =
        ords.iter().map(|o| (o.oid.clone(), o)).collect();
    let seq: HashMap<String, i64> =
        ords.iter().enumerate().map(|(i, o)| (o.oid.clone(), i as i64)).collect();

    let mut eff: HashMap<String, i64> = ords.iter()
        .map(|o| {
            let std = stdoffs.get(&o.oid).copied().unwrap_or(meta.meridian_seconds);
            (o.oid.clone(), to_ut(o.eff_civil, o.eff_anchor, std, 0))
        })
        .collect();

    let mut converged = false;
    for _ in 0..16 {
        let segments = segments_from(ords, &eff, &seq, &stdoffs)?;
        let mut next: HashMap<String, i64> = HashMap::new();
        for o in ords {
            let seg = governing_at(&segments, eff[&o.oid] - 1);
            next.insert(o.oid.clone(), effective_instant(
                o, seg, &by_id, &stdoffs, meta.meridian_seconds, eff[&o.oid]));
        }
        if next == eff {
            converged = true;
            break;
        }
        eff = next;
    }
    if !converged {
        return Err(format!("anchor fixpoint did not converge for {}", meta.zone).into());
    }
    let segments = segments_from(ords, &eff, &seq, &stdoffs)?;

    let mut transitions: Vec<Transition> = Vec::new();
    let mut prev = (meta.meridian_seconds, 0u8, "LMT".to_string());

    for seg in &segments {
        if seg.start > HORIZON {
            break;
        }
        let g = by_id[&seg.ordinance];
        let stdoff = stdoffs[&g.oid];

        let (save, label, _) = state_of(g, stdoff, seg.start);
        let utoff = stdoff + save;
        let st = (utoff, u8::from(save != 0), label_for(&label, utoff));
        if st != prev {
            transitions.push(Transition {
                ut: seg.start, utoff: st.0, isdst: st.1, abbrev: st.2.clone(),
                anchor: g.eff_anchor, ordinance: g.oid.clone(),
            });
            prev = st;
        }

        if let Some(obs) = &g.observance {
            let hi = match seg.end {
                None => HORIZON,
                Some(e) => HORIZON.min(e - 1),
            };
            let y0 = year_of(seg.start) - 1;
            let y1 = year_of(hi) + 1;
            let mut evs: Vec<(i64, i32, String, Anchor)> = Vec::new();
            for y in y0..=y1 {
                for (ut, save, label, anchor) in obs.events_for_year(stdoff, y) {
                    evs.push((ut, save, label.to_string(), anchor));
                }
            }
            evs.sort_by_key(|e| e.0);
            for (ut, save, label, anchor) in evs {
                if ut <= seg.start || ut > hi {
                    continue;
                }
                let utoff = stdoff + save;
                let st = (utoff, u8::from(save != 0), label_for(&label, utoff));
                if st != prev {
                    transitions.push(Transition {
                        ut, utoff: st.0, isdst: st.1, abbrev: st.2.clone(),
                        anchor, ordinance: g.oid.clone(),
                    });
                    prev = st;
                }
            }
        }
    }

    for w in transitions.windows(2) {
        if w[1].ut <= w[0].ut {
            return Err(format!("{}: non-monotonic transitions", meta.zone).into());
        }
    }

    let (types, _) = zone_types(meta.meridian_seconds, &transitions);

    let (final_oid, final_stdoff) = {
        let final_seg = segments.iter().rev().find(|s| s.start <= HORIZON)
            .ok_or("no governing ordinance at the horizon")?;
        if final_seg.end.is_some() {
            return Err("the ordinance governing the horizon is repealed".into());
        }
        (final_seg.ordinance.clone(), final_seg.stdoff)
    };
    let footer = footer_string(by_id[&final_oid], final_stdoff)?;

    let ordinances = ords.iter().map(|o| ResolvedOrd {
        oid: o.oid.clone(),
        kind: o.kind,
        enacted_text: o.enacted_text.clone(),
        enactment_seq: seq[&o.oid],
        effective_epoch: eff[&o.oid],
        effective_anchor: o.eff_anchor,
        standard_offset: stdoffs.get(&o.oid).copied(),
        basis: o.basis.clone(),
        repeals: o.repeals.clone(),
    }).collect();

    let perp = by_id[&final_oid];
    Ok(Zone {
        name: meta.zone.clone(),
        meridian: meta.meridian_seconds,
        transitions,
        segments,
        types,
        footer,
        ordinances,
        perpetual: perp.observance.clone(),
        perpetual_stdoff: final_stdoff,
        perpetual_label: perp.std_label.clone().unwrap_or_default(),
        perpetual_anchor: perp.eff_anchor,
    })
}

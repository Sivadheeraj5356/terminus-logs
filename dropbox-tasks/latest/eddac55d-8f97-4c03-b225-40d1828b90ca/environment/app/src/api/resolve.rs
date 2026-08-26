use crate::timeline::Zone;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind { Unique, Fold, Gap }

impl Kind {
    pub fn as_str(&self) -> &'static str {
        match self {
            Kind::Unique => "unique",
            Kind::Fold => "fold",
            Kind::Gap => "gap",
        }
    }
}

fn candidate_offsets(zone: &Zone) -> Vec<i32> {
    let mut offs = vec![zone.meridian, zone.perpetual_stdoff];
    if let Some(obs) = &zone.perpetual {
        offs.push(zone.perpetual_stdoff + obs.begin.save);
    }
    offs.extend(zone.transitions.iter().map(|t| t.utoff));
    offs.sort_unstable();
    offs.dedup();
    offs
}

/// Maps a naive local instant to UT. A gap under the reject policy yields None; under
/// the shift policy the instant is read against the offset in force before the gap.
pub fn resolve_local(zone: &Zone, local: i64, policy: &str, fold: u8)
    -> Option<(i64, Kind)>
{
    let mut cands: Vec<i64> = candidate_offsets(zone)
        .into_iter()
        .map(|u| local - u as i64)
        .filter(|t| zone.local_at(*t).0 as i64 == local - *t)
        .collect();
    cands.sort_unstable();
    cands.dedup();

    match cands.len() {
        1 => Some((cands[0], Kind::Unique)),
        0 => {
            if policy == "reject" {
                return None;
            }
            let before = zone.offsets_before();
            for (tr, prev) in zone.transitions.iter().zip(before) {
                if tr.utoff > prev
                    && tr.ut + prev as i64 <= local
                    && local < tr.ut + tr.utoff as i64
                {
                    return Some((local - prev as i64, Kind::Gap));
                }
            }
            None
        }
        _ => {
            let pick = if fold == 0 { cands[0] } else { *cands.last().unwrap() };
            Some((pick, Kind::Fold))
        }
    }
}

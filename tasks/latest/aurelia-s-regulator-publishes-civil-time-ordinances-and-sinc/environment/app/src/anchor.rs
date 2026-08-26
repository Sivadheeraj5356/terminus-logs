use std::collections::HashMap;

use crate::calendar::recur::to_ut;
use crate::corpus::Ordinance;
use crate::precedence::Segment;

/// The UT instant an ordinance takes effect.
///
/// The offset table recorded every time against the offset the row itself established,
/// because rows were transcribed from published local times after the change.
pub fn effective_instant(
    o: &Ordinance,
    _seg: Option<&Segment>,
    _by_id: &HashMap<String, &Ordinance>,
    stdoffs: &HashMap<String, i32>,
    meridian: i32,
    _guess: i64,
) -> i64 {
    let stdoff = stdoffs.get(&o.oid).copied().unwrap_or(meridian);
    to_ut(o.eff_civil, o.eff_anchor, stdoff, 0)
}

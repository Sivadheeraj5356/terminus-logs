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

/// 0 = Sunday.
pub fn weekday_from_days(z: i64) -> i64 {
    (z + 4) % 7
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
            last - (weekday_from_days(z) - spec.weekday) % 7
        }
        DayKind::Ge => {
            let z = days_from_civil(y, m, spec.day);
            spec.day + (spec.weekday - weekday_from_days(z)) % 7
        }
        DayKind::Le => {
            let z = days_from_civil(y, m, spec.day);
            spec.day - (weekday_from_days(z) - spec.weekday) % 7
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

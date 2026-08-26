//! Resolving the `a` and `mx` mechanisms to a match decision. Frozen evidence.

use crate::lookup::{a_records, mx_ips};
use crate::zone::Zone;

/// The domain an `a`/`mx` mechanism resolves against: an explicit `a:<d>` names
/// its own domain, a bare `a` takes the subject of the evaluation.
fn target<'a>(arg: &'a Option<String>, request: &'a str) -> &'a str {
    match arg {
        Some(d) => d,
        None => request,
    }
}

pub fn a_match(zone: &Zone, arg: &Option<String>, request: &str, ip: u32) -> bool {
    a_records(zone, target(arg, request)).contains(&ip)
}

pub fn mx_match(zone: &Zone, arg: &Option<String>, request: &str, ip: u32) -> bool {
    mx_ips(zone, target(arg, request)).contains(&ip)
}

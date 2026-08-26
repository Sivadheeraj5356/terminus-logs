//! Zone address lookups behind the `a` and `mx` mechanisms. Frozen evidence.

use crate::ip::parse_ip;
use crate::zone::Zone;

pub fn a_records(zone: &Zone, domain: &str) -> Vec<u32> {
    match zone.get(domain) {
        Some(rec) => rec.a.iter().filter_map(|s| parse_ip(s)).collect(),
        None => Vec::new(),
    }
}

pub fn mx_ips(zone: &Zone, domain: &str) -> Vec<u32> {
    let mut out = Vec::new();
    if let Some(rec) = zone.get(domain) {
        for host in &rec.mx {
            out.extend(a_records(zone, host));
        }
    }
    out
}

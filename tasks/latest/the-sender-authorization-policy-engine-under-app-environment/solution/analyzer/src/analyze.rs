//! The differential decision.
//!
//! One evaluator, parameterized by which of the engine's departures from
//! docs/sap-spec.md Part 1 are switched on. `INTENDED` turns them all off and is
//! Part 1 verbatim; `DEPLOYED` turns them all on and is what the frozen engine
//! computes. The four are recovered by reading engine/src:
//!
//!   req    - ctx.rs `delegate()` rebinds `request` to the target, so a policy
//!            reached through `redirect=` resolves a bare `a`/`mx` against the
//!            redirect target. `include:` passes its context through unchanged.
//!   budget - eval.rs charges `a`, `mx` and `include`, but the redirect arm has
//!            no charge at all, so a redirect term is free.
//!   last   - eval.rs records every match into `settled` and never returns
//!            early, so the LAST matching directive settles the result.
//!   cidr   - cidr.rs `mask()` consumes the prefix a whole octet at a time and
//!            drops the leftover bits, so /25..31 behave as /24, and so on.

use crate::model::{Mech, Query, Zone};
use crate::parse::{parse_ip, parse_policy};

const LOOKUP_LIMIT: u32 = 8;
const MAX_DELEGATION: u32 = 32;

struct Budget {
    used: u32,
}

impl Budget {
    fn new() -> Budget {
        Budget { used: 0 }
    }
    /// false once the budget is exhausted.
    fn charge(&mut self) -> bool {
        self.used += 1;
        self.used <= LOOKUP_LIMIT
    }
}

#[derive(Clone, Copy)]
struct Faults {
    req: bool,
    budget: bool,
    last: bool,
    cidr: bool,
}

const INTENDED: Faults = Faults {
    req: false,
    budget: false,
    last: false,
    cidr: false,
};

const DEPLOYED: Faults = Faults {
    req: true,
    budget: true,
    last: true,
    cidr: true,
};

fn qmap(q: char) -> &'static str {
    match q {
        '-' => "FAIL",
        '~' => "SOFTFAIL",
        '?' => "NEUTRAL",
        _ => "PASS",
    }
}

fn a_records(zone: &Zone, domain: &str) -> Vec<u32> {
    match zone.get(domain) {
        Some(rec) => rec.a.iter().filter_map(|s| parse_ip(s)).collect(),
        None => Vec::new(),
    }
}

fn mx_ips(zone: &Zone, domain: &str) -> Vec<u32> {
    let mut out = Vec::new();
    if let Some(rec) = zone.get(domain) {
        for host in &rec.mx {
            out.extend(a_records(zone, host));
        }
    }
    out
}

fn cidr_contains(ip: u32, net: u32, prefix: u8, f: Faults) -> bool {
    let p = if f.cidr { (prefix / 8) * 8 } else { prefix };
    if p == 0 {
        return true;
    }
    let shift = 32 - p as u32;
    (ip >> shift) == (net >> shift)
}

/// (result, settling token). PERMERROR propagates outward exactly as the engine
/// propagates it.
fn eval(
    zone: &Zone,
    current: &str,
    request: &str,
    ip: u32,
    budget: &mut Budget,
    f: Faults,
    depth: u32,
) -> (String, Option<String>) {
    if depth > MAX_DELEGATION {
        return ("PERMERROR".to_string(), None);
    }
    let rec = match zone.get(current) {
        Some(r) => r,
        None => return ("NONE".to_string(), None),
    };
    let sap = match &rec.sap {
        Some(s) => s,
        None => return ("NONE".to_string(), None),
    };
    let pol = match parse_policy(sap) {
        Ok(p) => p,
        Err(_) => return ("PERMERROR".to_string(), None),
    };

    let mut settled: Option<(String, String)> = None;

    for t in &pol.directives {
        let matched = match &t.mech {
            Mech::All => true,
            Mech::Ip4 { net, prefix } => cidr_contains(ip, *net, *prefix, f),
            Mech::A(arg) => {
                if !budget.charge() {
                    return ("PERMERROR".to_string(), None);
                }
                let target = arg.as_deref().unwrap_or(request);
                a_records(zone, target).contains(&ip)
            }
            Mech::Mx(arg) => {
                if !budget.charge() {
                    return ("PERMERROR".to_string(), None);
                }
                let target = arg.as_deref().unwrap_or(request);
                mx_ips(zone, target).contains(&ip)
            }
            Mech::Include(d) => {
                if !budget.charge() {
                    return ("PERMERROR".to_string(), None);
                }
                let (r, _) = eval(zone, d, request, ip, budget, f, depth + 1);
                if r == "PERMERROR" {
                    return ("PERMERROR".to_string(), None);
                }
                r == "PASS"
            }
        };
        if matched {
            let s = (qmap(t.qual).to_string(), t.raw.clone());
            if !f.last {
                return (s.0, Some(s.1));
            }
            settled = Some(s);
        }
    }

    if let Some((r, tok)) = settled {
        return (r, Some(tok));
    }

    if let Some(rd) = &pol.redirect {
        if !pol.has_all {
            if !f.budget && !budget.charge() {
                return ("PERMERROR".to_string(), None);
            }
            let sub: &str = if f.req { rd.as_str() } else { request };
            let (r, tok) = eval(zone, rd, sub, ip, budget, f, depth + 1);
            if r == "NONE" {
                return ("PERMERROR".to_string(), None);
            }
            return (r, tok);
        }
    }
    ("NEUTRAL".to_string(), None)
}

fn run(zone: &Zone, q: &Query, f: Faults) -> (String, Option<String>) {
    let mut b = Budget::new();
    eval(zone, &q.domain, &q.domain, q.ip, &mut b, f, 0)
}

pub fn analyze_query(zone: &Zone, q: &Query) -> (String, String, bool, Option<String>) {
    let (deployed, _) = run(zone, q, DEPLOYED);
    let (intended, _) = run(zone, q, INTENDED);
    let divergent = deployed != intended;
    let witness = if divergent {
        // The authorizing side, per spec Part 2.
        let side = if deployed == "PASS" {
            DEPLOYED
        } else if intended == "PASS" {
            INTENDED
        } else {
            DEPLOYED
        };
        Some(run(zone, q, side).1.unwrap_or_else(|| "-".to_string()))
    } else {
        None
    };
    (deployed, intended, divergent, witness)
}

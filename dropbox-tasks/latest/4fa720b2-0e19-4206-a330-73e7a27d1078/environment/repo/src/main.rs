// Cryostat boil-off warden: replays a stream of per-cryostat over-pressure-state
// events against a continuous-time monitor and emits, for each cryostat, the
// closed boil-off intervals (relief pressure sustained past the grace allowance)
// plus the total active at-risk time. At-risk time accrues at one unit per active
// second while the cryostat dwells above its relief threshold and no transfer-line
// purge is in progress. Reads {"grace":G,"events":[...]} from stdin and writes
// {"audit":[...],"boiloff":[...],"cryostats":{...}} to stdout.
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::io::{self, Read};

#[derive(Debug, Deserialize)]
struct Event {
    #[serde(rename = "type")]
    kind: String,
    cryostat: String,
    t: i64,
}

#[derive(Debug, Deserialize)]
struct Input {
    grace: i64,
    events: Vec<Event>,
}

#[derive(Debug, Serialize)]
struct AuditEntry {
    index: usize,
    #[serde(rename = "type")]
    kind: String,
    cryostat: String,
    t: i64,
    status: String,
}

#[derive(Debug, Serialize)]
struct BoiloffOut {
    cryostat: String,
    start: i64,
    end: i64,
}

#[derive(Debug, Serialize)]
struct CryostatOut {
    exposed: i64,
}

#[derive(Debug, Serialize)]
struct Output {
    audit: Vec<AuditEntry>,
    boiloff: Vec<BoiloffOut>,
    cryostats: BTreeMap<String, CryostatOut>,
}

struct State {
    at_risk: bool,
    purging: bool,
    risk_t: i64, // wall time the current over-pressure stretch began
    last_t: i64,
    has_last: bool,
    exposed: i64,
    boiloff: Vec<(i64, i64)>,
}

impl State {
    fn new() -> Self {
        State {
            at_risk: false,
            purging: false,
            risk_t: 0,
            last_t: 0,
            has_last: false,
            exposed: 0,
            boiloff: Vec::new(),
        }
    }
}

fn main() {
    let mut buf = String::new();
    io::stdin().read_to_string(&mut buf).unwrap();
    let input: Input = match serde_json::from_str(&buf) {
        Ok(v) => v,
        Err(_) => std::process::exit(1),
    };
    let grace = input.grace;

    let mut cryostats: BTreeMap<String, State> = BTreeMap::new();

    // advance accrues at-risk time between events into the running total.
    fn advance(s: &mut State, now: i64) {
        if !s.has_last {
            s.has_last = true;
            s.last_t = now;
            return;
        }
        if now <= s.last_t {
            s.last_t = now;
            return;
        }
        if s.at_risk {
            s.exposed += now - s.last_t;
        }
        s.last_t = now;
    }

    // close_boiloff decides, at an explicit press_low/report event, whether the
    // just-ended (or ongoing) over-pressure stretch ran past the grace allowance
    // and, if so, records the boil-off interval. It is measured from the press_high
    // plus the allowance, up to the closing instant.
    fn close_boiloff(s: &mut State, grace: i64, end: i64) {
        let exposed = end - s.risk_t;
        if exposed >= grace {
            let start = s.risk_t + grace;
            s.boiloff.push((start, end));
        }
    }

    let mut audit: Vec<AuditEntry> = Vec::new();
    for (i, ev) in input.events.iter().enumerate() {
        let s = cryostats.entry(ev.cryostat.clone()).or_insert_with(State::new);
        advance(s, ev.t);
        let mut status = "accepted";
        match ev.kind.as_str() {
            "press_high" => {
                if !s.at_risk {
                    s.at_risk = true;
                    s.risk_t = ev.t;
                }
            }
            "press_low" => {
                if s.at_risk {
                    close_boiloff(s, grace, ev.t);
                    s.at_risk = false;
                }
            }
            "purge_on" => {
                s.purging = true;
            }
            "purge_off" => {
                s.purging = false;
            }
            "report" => {
                if s.at_risk {
                    close_boiloff(s, grace, ev.t);
                }
            }
            _ => {
                status = "rejected";
            }
        }
        audit.push(AuditEntry {
            index: i,
            kind: ev.kind.clone(),
            cryostat: ev.cryostat.clone(),
            t: ev.t,
            status: status.to_string(),
        });
    }

    let mut boiloff: Vec<BoiloffOut> = Vec::new();
    for (name, s) in cryostats.iter() {
        for &(start, end) in &s.boiloff {
            boiloff.push(BoiloffOut {
                cryostat: name.clone(),
                start,
                end,
            });
        }
    }
    boiloff.sort_by(|a, b| {
        a.cryostat
            .cmp(&b.cryostat)
            .then(a.start.cmp(&b.start))
            .then(a.end.cmp(&b.end))
    });

    let mut cryostats_out: BTreeMap<String, CryostatOut> = BTreeMap::new();
    for (name, s) in cryostats.iter() {
        cryostats_out.insert(
            name.clone(),
            CryostatOut {
                exposed: s.exposed,
            },
        );
    }

    let out = Output {
        audit,
        boiloff,
        cryostats: cryostats_out,
    };
    println!("{}", serde_json::to_string(&out).unwrap());
}

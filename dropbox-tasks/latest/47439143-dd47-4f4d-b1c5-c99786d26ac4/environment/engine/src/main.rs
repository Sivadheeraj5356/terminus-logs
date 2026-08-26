//! Sender Authorization Policy engine.
//!
//! Reads a case file (JSON) whose path is the single argument, evaluates every
//! query against the zone, and prints one `"<id>\t<result>"` line per query to
//! stdout. A result is one of PASS, FAIL, SOFTFAIL, NEUTRAL, NONE, PERMERROR.
//!
//! This is the policy decision core as deployed. It is frozen evidence.

mod budget;
mod cidr;
mod ctx;
mod error;
mod eval;
mod include;
mod ip;
mod json;
mod lookup;
mod mechanism;
mod policy;
mod query;
mod resolve;
mod result;
mod term;
mod zone;

use budget::Budget;
use ctx::Ctx;
use query::Query;
use result::SapResult;
use std::env;
use std::fs;
use std::process;
use zone::Zone;

fn main() {
    let path = match env::args().nth(1) {
        Some(p) => p,
        None => {
            eprintln!("usage: mailgate <case.json>");
            process::exit(2);
        }
    };
    let data = fs::read(&path).expect("read case");
    let mut p = json::P::new(&data);
    let case = p.value();

    let zone = Zone::from_json(case.get("zone").expect("zone"));
    if let Some(qs) = case.get("queries") {
        for qj in qs.arr() {
            let q = Query::from_json(qj);
            let res = match q.ip {
                Some(ip) => evaluate_query(&zone, &q.domain, ip),
                None => SapResult::PermError,
            };
            println!("{}\t{}", q.id, res.name());
        }
    }
}

fn evaluate_query(zone: &Zone, domain: &str, ip: u32) -> SapResult {
    let mut budget = Budget::new();
    let ctx = Ctx::new(domain, ip);
    eval::evaluate(zone, domain, &ctx, &mut budget, 0).0
}

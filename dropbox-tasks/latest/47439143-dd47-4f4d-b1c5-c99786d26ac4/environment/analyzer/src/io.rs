//! Case reading and certificate writing. Provided by the scaffold.

use crate::analyze::analyze_query;
use crate::json::{Json, P};
use crate::model::{Cert, Query, Rec, Zone};
use crate::parse::parse_ip;
use std::collections::HashMap;
use std::fs;

fn zone_from_json(j: &Json) -> Zone {
    let mut map = HashMap::new();
    if let Some(obj) = j.obj() {
        for (dom, rec) in obj {
            let sap = rec.get("sap").map(|v| v.s().to_string());
            let a = rec
                .get("a")
                .map(|v| v.arr().iter().map(|x| x.s().to_string()).collect())
                .unwrap_or_default();
            let mx = rec
                .get("mx")
                .map(|v| v.arr().iter().map(|x| x.s().to_string()).collect())
                .unwrap_or_default();
            map.insert(dom.clone(), Rec { sap, a, mx });
        }
    }
    Zone { map }
}

fn esc(s: &str) -> String {
    let mut o = String::new();
    for c in s.chars() {
        match c {
            '"' => o.push_str("\\\""),
            '\\' => o.push_str("\\\\"),
            '\n' => o.push_str("\\n"),
            '\t' => o.push_str("\\t"),
            '\r' => o.push_str("\\r"),
            _ => o.push(c),
        }
    }
    o
}

fn cert_json(c: &Cert) -> String {
    let w = match &c.witness {
        Some(t) => format!("\"{}\"", esc(t)),
        None => "null".to_string(),
    };
    format!(
        "{{\"id\":\"{}\",\"deployed\":\"{}\",\"intended\":\"{}\",\"divergent\":{},\"witness\":{}}}",
        esc(&c.id),
        esc(&c.deployed),
        esc(&c.intended),
        c.divergent,
        w
    )
}

pub fn run(path: &str) {
    let data = fs::read(path).expect("read case");
    let mut p = P::new(&data);
    let case = p.value();
    let zone = zone_from_json(case.get("zone").expect("zone"));

    let mut certs = Vec::new();
    if let Some(qs) = case.get("queries") {
        for qj in qs.arr() {
            let id = qj.get("id").map(|v| v.s().to_string()).unwrap_or_default();
            let domain = qj.get("domain").map(|v| v.s().to_string()).unwrap_or_default();
            let ip = qj.get("ip").and_then(|v| parse_ip(v.s())).unwrap_or(0);
            let q = Query { id, domain, ip };
            let (deployed, intended, divergent, witness) = analyze_query(&zone, &q);
            certs.push(Cert {
                id: q.id,
                deployed,
                intended,
                divergent,
                witness,
            });
        }
    }

    let body: Vec<String> = certs.iter().map(cert_json).collect();
    println!("{{\"queries\":[{}]}}", body.join(","));
}

//! `dater` reads the sites, their recent coring record, and the chronology policy under
//! /app/environment/data, settles on a number of cores for each site, splits that number between
//! the shared field ration and the contract route, and prints the plan to stdout as JSON. Invoke
//! it as `./bin/dater data`.

// A few parsed fields ride along only for schema fidelity and go unread; quiet that lint here.
#![allow(dead_code)]

use std::env;
use std::fs;
use std::process;

struct Site {
    id: String,
    sensitivity: f64,
    field_cost: f64,
    contract_cost: f64,
}

struct Policy {
    reference_sensitivity: f64,
    rate_min: f64,
    rate_max: f64,
    anchor_floor: f64,
    field_budget: i64,
}

struct Row {
    site_id: String,
    field_cores: i64,
    contract_cores: i64,
}

fn main() {
    let data_dir = env::args().nth(1).unwrap_or_else(|| "data".to_string());

    let sites = read_sites(&format!("{data_dir}/sites.csv"));
    let (cores, crossings) = read_log(&format!("{data_dir}/core_log.csv"), &sites);
    let pol = read_policy(&format!("{data_dir}/chronology_policy.json"));

    let rates = estimate_rates(&sites, &cores, &crossings, &pol);

    // Convert each site's estimated rate into a core count that meets the anchor floor, then draw
    // the shared field ration down first so only the overflow reaches the pricier contract route.
    let n: Vec<i64> = rates
        .iter()
        .map(|&p| cores_for(p, pol.anchor_floor))
        .collect();
    let plan = allocate(&sites, &n, pol.field_budget);

    println!("{}", render(&plan));
}

/// Estimates each site from its own log alone: (crossdates + 0.5) / (cores + 1), a smoothed
/// fraction that stays defined even on an empty record, then clipped into the policy's
/// `[rate_min, rate_max]` band.
fn estimate_rates(sites: &[Site], cores: &[i64], crossings: &[i64], pol: &Policy) -> Vec<f64> {
    (0..sites.len())
        .map(|i| {
            let p = (crossings[i] as f64 + 0.5) / (cores[i] as f64 + 1.0);
            clamp(p, pol.rate_min, pol.rate_max)
        })
        .collect()
}

/// Smallest core count that lifts the anchor chance 1-(1-p)^n to the target.
fn cores_for(p: f64, target: f64) -> i64 {
    let p = clamp(p, 1e-6, 0.999999);
    ((1.0 - target).ln() / (1.0 - p).ln()).ceil() as i64
}

/// Spends the shared field ration before any contract core is booked. Sites are visited in order
/// of how far contract runs above field for them, each taking field cores until the ration is
/// gone; whatever a site still needs beyond that is charged to the contract route.
fn allocate(sites: &[Site], n: &[i64], field_budget: i64) -> Vec<Row> {
    let mut order: Vec<usize> = (0..sites.len()).collect();
    order.sort_by(|&a, &b| {
        let sa = sites[a].contract_cost - sites[a].field_cost;
        let sb = sites[b].contract_cost - sites[b].field_cost;
        sb.partial_cmp(&sa).unwrap()
    });
    let mut remaining = field_budget;
    let mut field = vec![0i64; sites.len()];
    for &i in &order {
        let mut take = n[i];
        if take > remaining {
            take = remaining;
        }
        if take < 0 {
            take = 0;
        }
        field[i] = take;
        remaining -= take;
    }
    (0..sites.len())
        .map(|i| Row {
            site_id: sites[i].id.clone(),
            field_cores: field[i],
            contract_cores: n[i] - field[i],
        })
        .collect()
}

fn render(plan: &[Row]) -> String {
    let mut s = String::from("{\n  \"plan\": [\n");
    for (i, r) in plan.iter().enumerate() {
        s.push_str(&format!(
            "    {{\"site_id\": \"{}\", \"field_cores\": {}, \"contract_cores\": {}}}",
            r.site_id, r.field_cores, r.contract_cores
        ));
        s.push_str(if i + 1 < plan.len() { ",\n" } else { "\n" });
    }
    s.push_str("  ]\n}");
    s
}

fn clamp(x: f64, lo: f64, hi: f64) -> f64 {
    x.max(lo).min(hi)
}

// ---- data-file parsing ----

fn read_sites(path: &str) -> Vec<Site> {
    let text = slurp(path);
    let mut sites = Vec::new();
    for line in text.lines().skip(1) {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let f: Vec<&str> = line.split(',').collect();
        sites.push(Site {
            id: f[0].trim().to_string(),
            sensitivity: atof(f[1]),
            field_cost: atof(f[2]),
            contract_cost: atof(f[3]),
        });
    }
    sites
}

fn read_log(path: &str, sites: &[Site]) -> (Vec<i64>, Vec<i64>) {
    let mut cores = vec![0i64; sites.len()];
    let mut crossings = vec![0i64; sites.len()];
    let text = slurp(path);
    for line in text.lines().skip(1) {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let f: Vec<&str> = line.split(',').collect();
        if let Some(i) = sites.iter().position(|c| c.id == f[0].trim()) {
            cores[i] += 1;
            if f[1].trim() == "1" {
                crossings[i] += 1;
            }
        }
    }
    (cores, crossings)
}

fn read_policy(path: &str) -> Policy {
    let text = slurp(path);
    Policy {
        reference_sensitivity: json_number(&text, "reference_sensitivity"),
        rate_min: json_number(&text, "cross_rate_min"),
        rate_max: json_number(&text, "cross_rate_max"),
        anchor_floor: json_number(&text, "anchor_floor"),
        field_budget: json_number(&text, "field_core_budget") as i64,
    }
}

/// Pulls the number sitting after `"<key>":` out of the small policy file. With a single flat
/// object in play, scanning for the key as a substring is enough and needs no JSON crate.
fn json_number(text: &str, key: &str) -> f64 {
    let needle = format!("\"{key}\"");
    let start = text.find(&needle).unwrap_or_else(|| die(&format!("missing key {key}")));
    let after = &text[start + needle.len()..];
    let colon = after.find(':').unwrap_or_else(|| die(&format!("malformed key {key}")));
    let tail = &after[colon + 1..];
    let num: String = tail
        .trim_start()
        .chars()
        .take_while(|c| c.is_ascii_digit() || *c == '.' || *c == '-' || *c == '+' || *c == 'e' || *c == 'E')
        .collect();
    num.parse().unwrap_or_else(|_| die(&format!("bad number for {key}")))
}

fn slurp(path: &str) -> String {
    fs::read_to_string(path).unwrap_or_else(|e| die(&format!("{path}: {e}")))
}

fn atof(s: &str) -> f64 {
    s.trim().parse().unwrap_or_else(|_| die(&format!("bad float: {s}")))
}

fn die(msg: &str) -> ! {
    eprintln!("dater: {msg}");
    process::exit(1);
}

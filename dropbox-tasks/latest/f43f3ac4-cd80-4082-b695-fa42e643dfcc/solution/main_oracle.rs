//! Oracle `dater`, dropped in for environment/main.rs. It ignores each site's own cores and
//! instead regresses the whole network's logged crossdate rate on sensitivity by weighted least
//! squares. Every site is then handed the fitted value walked down Z_PRED prediction SDs, its
//! band's low edge. Because even a near-empty site inherits that walked-down edge, no single site
//! drags the joint floor down, and the counts settle just over it.

use std::env;
use std::fs;
use std::process;

const Z_PRED: f64 = 3.0;
// Size to a target set above the anchor floor, leaving room for the weakest site to still clear
// the floor when it is scored on a fresh season. FLOOR_HEADROOM picks that target as a fraction
// of the way from the floor to full certainty: at 0.6 it turns a 0.95 floor into a 0.970 aim.
const FLOOR_HEADROOM: f64 = 0.6;

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
    cost_ceiling: f64,
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

    let target = 1.0 - (1.0 - pol.anchor_floor) * FLOOR_HEADROOM;
    let n: Vec<i64> = rates.iter().map(|&p| cores_for(p, target)).collect();
    let plan = allocate(&sites, &n, pol.field_budget);

    enforce_policy(&plan, &sites, &rates, &n, &pol);

    println!("{}", render(&plan));
}

/// Refuses to emit a plan that violates either rule. Checked on the rate each site was sized
/// against, no site's anchor chance 1-(1-p)^n may fall under the floor, and the field-plus-
/// contract cost total may not top the ceiling; the first violation aborts before any output.
fn enforce_policy(plan: &[Row], sites: &[Site], rates: &[f64], n: &[i64], pol: &Policy) {
    for i in 0..sites.len() {
        let anchor = 1.0 - (1.0 - rates[i]).powi(n[i] as i32);
        if anchor < pol.anchor_floor {
            die(&format!(
                "site {} under anchor floor: {:.4} < {:.4}",
                sites[i].id, anchor, pol.anchor_floor
            ));
        }
    }
    let mut cost = 0.0;
    for (i, r) in plan.iter().enumerate() {
        cost += r.field_cores as f64 * sites[i].field_cost;
        cost += r.contract_cores as f64 * sites[i].contract_cost;
    }
    if cost > pol.cost_ceiling {
        die(&format!("committed cost {:.2} over ceiling {:.2}", cost, pol.cost_ceiling));
    }
}

/// Fits log(crossdate rate) on (sensitivity - reference) across the forty sites by weighted least
/// squares, then returns for each the fitted value minus Z_PRED standard deviations. That
/// subtraction is the whole point: a site with few or zero logged crossdates cannot speak for
/// itself, so it leans on the network fit lowered by a safety step rather than its own bare count.
fn estimate_rates(sites: &[Site], cores: &[i64], crossings: &[i64], pol: &Policy) -> Vec<f64> {
    let n = sites.len();
    let mut delta = vec![0.0f64; n];
    let mut y = vec![0.0f64; n];
    let mut w = vec![0.0f64; n];
    let (mut s1, mut sx, mut sxx, mut sy, mut sxy) = (0.0, 0.0, 0.0, 0.0, 0.0);
    for i in 0..n {
        let ph = (crossings[i] as f64 + 0.5) / (cores[i] as f64 + 1.0);
        delta[i] = sites[i].sensitivity - pol.reference_sensitivity;
        y[i] = ph.ln();
        w[i] = cores[i] as f64 * ph * (1.0 - ph);
        s1 += w[i];
        sx += w[i] * delta[i];
        sxx += w[i] * delta[i] * delta[i];
        sy += w[i] * y[i];
        sxy += w[i] * delta[i] * y[i];
    }
    let det = s1 * sxx - sx * sx;
    let b0 = (sxx * sy - sx * sxy) / det;
    let b1 = (s1 * sxy - sx * sy) / det;

    let mut wr2 = 0.0;
    let mut wsum = 0.0;
    for i in 0..n {
        let r = y[i] - (b0 + b1 * delta[i]);
        wr2 += w[i] * r * r;
        wsum += w[i];
    }
    let s2 = wr2 / wsum * n as f64 / (n as f64 - 2.0);

    (0..n)
        .map(|i| {
            let v_mean = (sxx - 2.0 * delta[i] * sx + delta[i] * delta[i] * s1) / det;
            let sd = (v_mean + s2).max(0.0).sqrt();
            let theta = (b0 + b1 * delta[i] - Z_PRED * sd).exp();
            clamp(theta, pol.rate_min, pol.rate_max)
        })
        .collect()
}

fn cores_for(p: f64, target: f64) -> i64 {
    let p = clamp(p, 1e-6, 0.999999);
    ((1.0 - target).ln() / (1.0 - p).ln()).ceil() as i64
}

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
        cost_ceiling: json_number(&text, "cost_ceiling"),
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

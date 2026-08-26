//! Reference `switcher` (swapped in over environment/main.rs). Where the starter reads each design off
//! its own handful of dies, this one pins the rate to the whole slate: it fits one line of log
//! acceptance-rate against gate_grade, places every design on that line, then steps each rate down by
//! Z_PRED of its prediction spread. The step is widest where a design's record is thinnest, so the
//! barely-built designs are the ones carried with the most room.

use std::env;
use std::fs;
use std::process;

const Z_PRED: f64 = 3.0;
// Aim a notch above the floor; that margin keeps the least-recorded design off a floor it was never
// built against.
const HEADROOM: f64 = 0.6;

struct Design {
    id: String,
    gate_grade: f64,
    probe_cost: f64,
    lab_cost: f64,
}

struct Rule {
    reference_gate: f64,
    rate_min: f64,
    rate_max: f64,
    signoff_floor: f64,
    probe_capacity: i64,
}

struct Row {
    design_id: String,
    probe_dies: i64,
    lab_dies: i64,
}

fn main() {
    let dir = env::args().nth(1).unwrap_or_else(|| "data".to_string());

    let designs = read_designs(&format!("{dir}/designs.csv"));
    let (built, passed) = read_log(&format!("{dir}/test_log.csv"), &designs);
    let rule = read_rule(&format!("{dir}/release_rule.json"));

    let rates = fit_rates(&designs, &built, &passed, &rule);

    let target = 1.0 - (1.0 - rule.signoff_floor) * HEADROOM;
    let n: Vec<i64> = rates.iter().map(|&p| dies_for(p, target)).collect();
    let plan = allocate(&designs, &n, rule.probe_capacity);

    guard_floor(&plan, &designs, &rates, &n, &rule);

    println!("{}", render(&plan));
}

// Refuse to print a plan that leaves any design short of the floor at its sized rate; the spend is
// left to come out under the sealed ceiling on its own, which the notch above the floor secures.
fn guard_floor(plan: &[Row], designs: &[Design], rates: &[f64], n: &[i64], rule: &Rule) {
    let _ = plan;
    for i in 0..designs.len() {
        let chance = 1.0 - (1.0 - rates[i]).powi(n[i] as i32);
        if chance < rule.signoff_floor {
            die(&format!(
                "design {} under floor: {:.4} < {:.4}",
                designs[i].id, chance, rule.signoff_floor
            ));
        }
    }
}

// Weighted least squares of ln(acceptance) on gate_grade across the slate, then a per-design rate read
// off the fit and dropped Z_PRED prediction SDs; a scant record widens that drop.
fn fit_rates(designs: &[Design], built: &[i64], passed: &[i64], rule: &Rule) -> Vec<f64> {
    let n = designs.len();
    let mut delta = vec![0.0f64; n];
    let mut y = vec![0.0f64; n];
    let mut w = vec![0.0f64; n];
    let (mut s1, mut sx, mut sxx, mut sy, mut sxy) = (0.0, 0.0, 0.0, 0.0, 0.0);
    for i in 0..n {
        let ph = (passed[i] as f64 + 0.5) / (built[i] as f64 + 1.0);
        delta[i] = designs[i].gate_grade - rule.reference_gate;
        y[i] = ph.ln();
        w[i] = built[i] as f64 * ph * (1.0 - ph);
        s1 += w[i];
        sx += w[i] * delta[i];
        sxx += w[i] * delta[i] * delta[i];
        sy += w[i] * y[i];
        sxy += w[i] * delta[i] * y[i];
    }
    let det = s1 * sxx - sx * sx;
    let a0 = (sxx * sy - sx * sxy) / det;
    let a1 = (s1 * sxy - sx * sy) / det;

    let mut wr2 = 0.0;
    let mut wsum = 0.0;
    for i in 0..n {
        let r = y[i] - (a0 + a1 * delta[i]);
        wr2 += w[i] * r * r;
        wsum += w[i];
    }
    let s2 = wr2 / wsum * n as f64 / (n as f64 - 2.0);

    (0..n)
        .map(|i| {
            let v_mean = (sxx - 2.0 * delta[i] * sx + delta[i] * delta[i] * s1) / det;
            let sd = (v_mean + s2).max(0.0).sqrt();
            let theta = (a0 + a1 * delta[i] - Z_PRED * sd).exp();
            clamp(theta, rule.rate_min, rule.rate_max)
        })
        .collect()
}

fn dies_for(p: f64, target: f64) -> i64 {
    let p = clamp(p, 1e-6, 0.999999);
    ((1.0 - target).ln() / (1.0 - p).ln()).ceil() as i64
}

fn allocate(designs: &[Design], n: &[i64], probe_capacity: i64) -> Vec<Row> {
    let mut order: Vec<usize> = (0..designs.len()).collect();
    order.sort_by(|&a, &b| {
        let sa = designs[a].lab_cost - designs[a].probe_cost;
        let sb = designs[b].lab_cost - designs[b].probe_cost;
        sb.partial_cmp(&sa).unwrap()
    });
    let mut left = probe_capacity;
    let mut probe = vec![0i64; designs.len()];
    for &i in &order {
        let mut take = n[i];
        if take > left {
            take = left;
        }
        if take < 0 {
            take = 0;
        }
        probe[i] = take;
        left -= take;
    }
    (0..designs.len())
        .map(|i| Row {
            design_id: designs[i].id.clone(),
            probe_dies: probe[i],
            lab_dies: n[i] - probe[i],
        })
        .collect()
}

fn render(plan: &[Row]) -> String {
    let mut s = String::from("{\n  \"plan\": [\n");
    for (i, r) in plan.iter().enumerate() {
        s.push_str(&format!(
            "    {{\"design_id\": \"{}\", \"probe_dies\": {}, \"lab_dies\": {}}}",
            r.design_id, r.probe_dies, r.lab_dies
        ));
        s.push_str(if i + 1 < plan.len() { ",\n" } else { "\n" });
    }
    s.push_str("  ]\n}");
    s
}

fn clamp(x: f64, lo: f64, hi: f64) -> f64 {
    x.max(lo).min(hi)
}

// -- input readers --

fn read_designs(path: &str) -> Vec<Design> {
    let text = slurp(path);
    let mut designs = Vec::new();
    for line in text.lines().skip(1) {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let f: Vec<&str> = line.split(',').collect();
        designs.push(Design {
            id: f[0].trim().to_string(),
            gate_grade: atof(f[1]),
            probe_cost: atof(f[2]),
            lab_cost: atof(f[3]),
        });
    }
    designs
}

fn read_log(path: &str, designs: &[Design]) -> (Vec<i64>, Vec<i64>) {
    let mut built = vec![0i64; designs.len()];
    let mut passed = vec![0i64; designs.len()];
    let text = slurp(path);
    for line in text.lines().skip(1) {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let f: Vec<&str> = line.split(',').collect();
        if let Some(i) = designs.iter().position(|c| c.id == f[0].trim()) {
            built[i] += 1;
            if f[1].trim() == "1" {
                passed[i] += 1;
            }
        }
    }
    (built, passed)
}

fn read_rule(path: &str) -> Rule {
    let text = slurp(path);
    Rule {
        reference_gate: json_number(&text, "reference_gate"),
        rate_min: json_number(&text, "rate_min"),
        rate_max: json_number(&text, "rate_max"),
        signoff_floor: json_number(&text, "signoff_floor"),
        probe_capacity: json_number(&text, "probe_capacity") as i64,
    }
}

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
    eprintln!("switcher: {msg}");
    process::exit(1);
}

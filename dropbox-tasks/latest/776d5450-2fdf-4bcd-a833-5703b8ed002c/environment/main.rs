//! Starter for `switcher`. Given the slate, the log and the rule file, it emits a JSON plan that sets an
//! in-house die count and an outside die count for every design. The rate under those counts is the weak
//! link, and repairing it is the task: as written the rate comes off a design's own log by itself, so a
//! design with a die or two behind it is sized on next to nothing and slips below the floor. The repair
//! is a rate that leans on the whole slate instead of the one design.

// Two parsed fields go unused here.
#![allow(dead_code)]

use std::env;
use std::fs;
use std::process;

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

    let rates = own_log_rates(&designs, &built, &passed, &rule);

    // Counts sized to the floor; the capped in-house route goes where the price gap is widest and the
    // outside house takes the rest.
    let n: Vec<i64> = rates.iter().map(|&p| dies_for(p, rule.signoff_floor)).collect();
    let plan = allocate(&designs, &n, rule.probe_capacity);

    println!("{}", render(&plan));
}

// Own-log estimate: a smoothed pass fraction from this design's rows only, clamped to the rule's bounds.
// On a shallow record it is barely better than a guess, which is exactly the flaw to mend.
fn own_log_rates(designs: &[Design], built: &[i64], passed: &[i64], rule: &Rule) -> Vec<f64> {
    (0..designs.len())
        .map(|i| {
            let p = (passed[i] as f64 + 0.5) / (built[i] as f64 + 1.0);
            clamp(p, rule.rate_min, rule.rate_max)
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

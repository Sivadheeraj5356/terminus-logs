//! Reference `framer`. Where the starter trusts each subject's own frames, this one does not: it
//! regresses the whole shoot list's logged keeper rate on showiness by weighted least squares,
//! and returns for each subject a rate held Z_PRED prediction SDs under the fitted line. A subject
//! whose log is too thin to fix its own rate still rides that lowered line, and that is what keeps
//! the weakest subject over the joint floor. Counts land a hair past the floor. It takes the place
//! of environment/main.rs.

use std::env;
use std::fs;
use std::process;

const Z_PRED: f64 = 3.0;
// Aim a notch above the policy keeper floor so the weakest subject still clears it once the plan is
// scored on a fresh outing. FLOOR_HEADROOM is how much of the climb from the floor to a sure keeper
// the target holds in reserve; at a 0.95 floor that lands the sizing target on 0.970.
const FLOOR_HEADROOM: f64 = 0.6;

struct Subject {
    id: String,
    showiness: f64,
    hide_cost: f64,
    guide_cost: f64,
}

struct Policy {
    reference_showiness: f64,
    keeper_min: f64,
    keeper_max: f64,
    keeper_floor: f64,
    hide_budget: i64,
    cost_ceiling: f64,
}

struct Row {
    subject_id: String,
    hide_frames: i64,
    guided_frames: i64,
}

fn main() {
    let data_dir = env::args().nth(1).unwrap_or_else(|| "data".to_string());

    let subjects = read_subjects(&format!("{data_dir}/subjects.csv"));
    let (frames, keepers) = read_log(&format!("{data_dir}/frame_log.csv"), &subjects);
    let pol = read_policy(&format!("{data_dir}/shoot_policy.json"));

    let rates = estimate_rates(&subjects, &frames, &keepers, &pol);

    let target = 1.0 - (1.0 - pol.keeper_floor) * FLOOR_HEADROOM;
    let n: Vec<i64> = rates.iter().map(|&p| frames_for(p, target)).collect();
    let plan = allocate(&subjects, &n, pol.hide_budget);

    enforce_policy(&plan, &subjects, &rates, &n, &pol);

    println!("{}", render(&plan));
}

/// Bail out before printing if either posted limit is broken. Taken on the rate each subject was
/// sized against, its 1-(1-p)^n must sit at or above the floor, and the hide-plus-guide spend summed
/// over the plan must stay under the ceiling. A miss on either one exits the run with no plan.
fn enforce_policy(plan: &[Row], subjects: &[Subject], rates: &[f64], n: &[i64], pol: &Policy) {
    for i in 0..subjects.len() {
        let keep = 1.0 - (1.0 - rates[i]).powi(n[i] as i32);
        if keep < pol.keeper_floor {
            die(&format!(
                "subject {} under keeper floor: {:.4} < {:.4}",
                subjects[i].id, keep, pol.keeper_floor
            ));
        }
    }
    let mut cost = 0.0;
    for (i, r) in plan.iter().enumerate() {
        cost += r.hide_frames as f64 * subjects[i].hide_cost;
        cost += r.guided_frames as f64 * subjects[i].guide_cost;
    }
    if cost > pol.cost_ceiling {
        die(&format!("committed cost {:.2} over ceiling {:.2}", cost, pol.cost_ceiling));
    }
}

/// The keeper rate for each subject comes from the fleet, not its own frames: a weighted
/// least-squares fit of log rate on (showiness - reference), read Z_PRED prediction SDs low. Where a
/// record is too sparse to say much, the fitted low read stands in, and that substitution is what
/// stops the thinnest-logged subject from dragging the joint floor down.
fn estimate_rates(subjects: &[Subject], frames: &[i64], keepers: &[i64], pol: &Policy) -> Vec<f64> {
    let n = subjects.len();
    let mut delta = vec![0.0f64; n];
    let mut y = vec![0.0f64; n];
    let mut w = vec![0.0f64; n];
    let (mut s1, mut sx, mut sxx, mut sy, mut sxy) = (0.0, 0.0, 0.0, 0.0, 0.0);
    for i in 0..n {
        let ph = (keepers[i] as f64 + 0.5) / (frames[i] as f64 + 1.0);
        delta[i] = subjects[i].showiness - pol.reference_showiness;
        y[i] = ph.ln();
        w[i] = frames[i] as f64 * ph * (1.0 - ph);
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
            clamp(theta, pol.keeper_min, pol.keeper_max)
        })
        .collect()
}

fn frames_for(p: f64, target: f64) -> i64 {
    let p = clamp(p, 1e-6, 0.999999);
    ((1.0 - target).ln() / (1.0 - p).ln()).ceil() as i64
}

fn allocate(subjects: &[Subject], n: &[i64], hide_budget: i64) -> Vec<Row> {
    let mut order: Vec<usize> = (0..subjects.len()).collect();
    order.sort_by(|&a, &b| {
        let sa = subjects[a].guide_cost - subjects[a].hide_cost;
        let sb = subjects[b].guide_cost - subjects[b].hide_cost;
        sb.partial_cmp(&sa).unwrap()
    });
    let mut remaining = hide_budget;
    let mut hide = vec![0i64; subjects.len()];
    for &i in &order {
        let mut take = n[i];
        if take > remaining {
            take = remaining;
        }
        if take < 0 {
            take = 0;
        }
        hide[i] = take;
        remaining -= take;
    }
    (0..subjects.len())
        .map(|i| Row {
            subject_id: subjects[i].id.clone(),
            hide_frames: hide[i],
            guided_frames: n[i] - hide[i],
        })
        .collect()
}

fn render(plan: &[Row]) -> String {
    let mut s = String::from("{\n  \"plan\": [\n");
    for (i, r) in plan.iter().enumerate() {
        s.push_str(&format!(
            "    {{\"subject_id\": \"{}\", \"hide_frames\": {}, \"guided_frames\": {}}}",
            r.subject_id, r.hide_frames, r.guided_frames
        ));
        s.push_str(if i + 1 < plan.len() { ",\n" } else { "\n" });
    }
    s.push_str("  ]\n}");
    s
}

fn clamp(x: f64, lo: f64, hi: f64) -> f64 {
    x.max(lo).min(hi)
}

// ---- file parsing ----

fn read_subjects(path: &str) -> Vec<Subject> {
    let text = slurp(path);
    let mut subjects = Vec::new();
    for line in text.lines().skip(1) {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let f: Vec<&str> = line.split(',').collect();
        subjects.push(Subject {
            id: f[0].trim().to_string(),
            showiness: atof(f[1]),
            hide_cost: atof(f[2]),
            guide_cost: atof(f[3]),
        });
    }
    subjects
}

fn read_log(path: &str, subjects: &[Subject]) -> (Vec<i64>, Vec<i64>) {
    let mut frames = vec![0i64; subjects.len()];
    let mut keepers = vec![0i64; subjects.len()];
    let text = slurp(path);
    for line in text.lines().skip(1) {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let f: Vec<&str> = line.split(',').collect();
        if let Some(i) = subjects.iter().position(|c| c.id == f[0].trim()) {
            frames[i] += 1;
            if f[1].trim() == "1" {
                keepers[i] += 1;
            }
        }
    }
    (frames, keepers)
}

fn read_policy(path: &str) -> Policy {
    let text = slurp(path);
    Policy {
        reference_showiness: json_number(&text, "reference_showiness"),
        keeper_min: json_number(&text, "keeper_prob_min"),
        keeper_max: json_number(&text, "keeper_prob_max"),
        keeper_floor: json_number(&text, "keeper_floor"),
        hide_budget: json_number(&text, "hide_frame_budget") as i64,
        cost_ceiling: json_number(&text, "cost_ceiling"),
    }
}

/// Pulls the number that follows `"<key>":` out of the small flat policy object. One object, no
/// nesting, so scanning for the key beats pulling in a JSON crate.
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
    eprintln!("framer: {msg}");
    process::exit(1);
}

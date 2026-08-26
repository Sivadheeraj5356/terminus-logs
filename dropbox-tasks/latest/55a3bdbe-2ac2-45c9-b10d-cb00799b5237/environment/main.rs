//! A first-cut `framer`. For each of the forty photo subjects it reads a keeper rate straight off
//! that subject's own frame log, turns the rate into a frame count that meets the keeper floor,
//! and splits the count across the shared public-hide ration and the private-guide route before
//! printing the plan. The reference sizer under /solution stands in for this at grade time.
//! Invoke as `./bin/framer data`.

// The parsed row types carry every column; this quiets the warning for the ones left unread.
#![allow(dead_code)]

use std::env;
use std::fs;
use std::process;

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

    // Each rate becomes the fewest frames that carry a subject to the keeper floor; the shared
    // hide ration is drawn down first, and only what is left over is booked on the guide route.
    let n: Vec<i64> = rates
        .iter()
        .map(|&p| frames_for(p, pol.keeper_floor))
        .collect();
    let plan = allocate(&subjects, &n, pol.hide_budget);

    println!("{}", render(&plan));
}

/// Reads each subject's keeper rate off its own frame log: keepers over frames fired, nudged by a
/// half-count prior so a subject with a bare log still lands on a value, then confined to the
/// policy's `[keeper_prob_min, keeper_prob_max]` window.
fn estimate_rates(subjects: &[Subject], frames: &[i64], keepers: &[i64], pol: &Policy) -> Vec<f64> {
    (0..subjects.len())
        .map(|i| {
            let p = (keepers[i] as f64 + 0.5) / (frames[i] as f64 + 1.0);
            clamp(p, pol.keeper_min, pol.keeper_max)
        })
        .collect()
}

/// Fewest frames n whose keeper chance 1-(1-p)^n reaches the target.
fn frames_for(p: f64, target: f64) -> i64 {
    let p = clamp(p, 1e-6, 0.999999);
    ((1.0 - target).ln() / (1.0 - p).ln()).ceil() as i64
}

/// Spends the shared hide ration before any guide frame. Subjects are taken in order of how much
/// the hide route undercuts the guide route, each drawing hide frames until the ration empties;
/// anything a subject still needs after that is booked on the guide route.
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

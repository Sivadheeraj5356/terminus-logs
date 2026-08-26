//! Starter that reads no further than each design's own burns. It pulls the design board and the
//! burn record from a data directory and prints, for every design, how many candles to pour on
//! each of the two routes. The rate it works from is just the clean share in that one design's log,
//! nothing borrowed from the rest of the board; it converts that share to a count and fills the
//! in-house line first, taking designs in order of the widest line-to-shop price gap, then sends
//! whatever the shared pool will not hold to the outside chandler. Run it as `chandler data`.

// blend_grade is loaded for schema parity and goes unread in this own-log starter.
#![allow(dead_code)]

use std::env;
use std::fs;
use std::process;

/// A single design, plus the poured/clean tallies folded in from the burn record.
struct Candle {
    id: String,
    blend_grade: f64,
    cost_line: f64,
    cost_shop: f64,
    poured: i64,
    clean: i64,
}

impl Candle {
    /// Clean burns over poured candles, each nudged by a half so a design with an empty record
    /// still yields a number, then held inside the allowed band.
    fn own_rate(&self, lo: f64, hi: f64) -> f64 {
        let r = (self.clean as f64 + 0.5) / (self.poured as f64 + 1.0);
        clamp(r, lo, hi)
    }
}

struct Policy {
    reference_blend_grade: f64,
    rate_min: f64,
    rate_max: f64,
    burn_floor: f64,
    line_capacity: i64,
}

fn main() {
    let dir = env::args().nth(1).unwrap_or_else(|| "data".to_string());

    let mut candles = load_candles(&format!("{dir}/designs.csv"));
    fold_log(&format!("{dir}/burn_log.csv"), &mut candles);
    let pol = read_policy(&format!("{dir}/run_program.json"));

    // Size each design off its own logged share alone, with nothing carried across the board.
    let counts: Vec<i64> = candles
        .iter()
        .map(|c| candles_for(c.own_rate(pol.rate_min, pol.rate_max), pol.burn_floor))
        .collect();
    let plan = split_routes(&candles, &counts, pol.line_capacity);

    println!("{}", emit(&plan));
}

/// Smallest count of candles for which 1-(1-p)^n reaches the target.
fn candles_for(p: f64, target: f64) -> i64 {
    let p = clamp(p, 1e-6, 0.999999);
    ((1.0 - target).ln() / (1.0 - p).ln()).ceil() as i64
}

/// Ranks designs by how much staying off the outside chandler saves, shop price minus line price,
/// and spends the shared line pool down that ranking from the largest saving. When the pool runs
/// out a design's remaining candles fall to the uncapped shop.
fn split_routes(candles: &[Candle], counts: &[i64], line_capacity: i64) -> Vec<Row> {
    let mut order: Vec<usize> = (0..candles.len()).collect();
    order.sort_by(|&a, &b| {
        let ga = candles[a].cost_shop - candles[a].cost_line;
        let gb = candles[b].cost_shop - candles[b].cost_line;
        gb.partial_cmp(&ga).unwrap()
    });
    let mut left = line_capacity;
    let mut line = vec![0i64; candles.len()];
    for &i in &order {
        let take = counts[i].clamp(0, left);
        line[i] = take;
        left -= take;
    }
    (0..candles.len())
        .map(|i| Row {
            design_id: candles[i].id.clone(),
            line_pours: line[i],
            shop_pours: counts[i] - line[i],
        })
        .collect()
}

struct Row {
    design_id: String,
    line_pours: i64,
    shop_pours: i64,
}

fn emit(plan: &[Row]) -> String {
    let mut s = String::from("{\n  \"plan\": [\n");
    for (i, r) in plan.iter().enumerate() {
        s.push_str(&format!(
            "    {{\"design_id\": \"{}\", \"line_pours\": {}, \"shop_pours\": {}}}",
            r.design_id, r.line_pours, r.shop_pours
        ));
        s.push_str(if i + 1 < plan.len() { ",\n" } else { "\n" });
    }
    s.push_str("  ]\n}");
    s
}

fn clamp(x: f64, lo: f64, hi: f64) -> f64 {
    x.max(lo).min(hi)
}

// ---- readers ----

fn load_candles(path: &str) -> Vec<Candle> {
    let text = slurp(path);
    let mut candles = Vec::new();
    for line in text.lines().skip(1) {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let c: Vec<&str> = line.split(',').collect();
        candles.push(Candle {
            id: c[0].trim().to_string(),
            blend_grade: num_of(c[1]),
            cost_line: num_of(c[2]),
            cost_shop: num_of(c[3]),
            poured: 0,
            clean: 0,
        });
    }
    candles
}

/// Adds up each design's poured and clean counts from the flat burn record.
fn fold_log(path: &str, candles: &mut [Candle]) {
    let text = slurp(path);
    for line in text.lines().skip(1) {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let c: Vec<&str> = line.split(',').collect();
        if let Some(m) = candles.iter_mut().find(|m| m.id == c[0].trim()) {
            m.poured += 1;
            if c[1].trim() == "1" {
                m.clean += 1;
            }
        }
    }
}

fn read_policy(path: &str) -> Policy {
    let text = slurp(path);
    Policy {
        reference_blend_grade: num_field(&text, "reference_blend_grade"),
        rate_min: num_field(&text, "rate_min"),
        rate_max: num_field(&text, "rate_max"),
        burn_floor: num_field(&text, "burn_floor"),
        line_capacity: num_field(&text, "line_capacity") as i64,
    }
}

/// Pulls the number sitting after a named key in the flat policy text. A lone small file is not
/// worth pulling in a JSON parser for.
fn num_field(text: &str, key: &str) -> f64 {
    let needle = format!("\"{key}\"");
    let at = text.find(&needle).unwrap_or_else(|| die(&format!("missing key {key}")));
    let rest = &text[at + needle.len()..];
    let colon = rest.find(':').unwrap_or_else(|| die(&format!("malformed key {key}")));
    let digits: String = rest[colon + 1..]
        .trim_start()
        .chars()
        .take_while(|c| c.is_ascii_digit() || *c == '.' || *c == '-' || *c == '+' || *c == 'e' || *c == 'E')
        .collect();
    digits.parse().unwrap_or_else(|_| die(&format!("bad number for {key}")))
}

fn slurp(path: &str) -> String {
    fs::read_to_string(path).unwrap_or_else(|e| die(&format!("{path}: {e}")))
}

fn num_of(s: &str) -> f64 {
    s.trim().parse().unwrap_or_else(|_| die(&format!("bad float: {s}")))
}

fn die(msg: &str) -> ! {
    eprintln!("chandler: {msg}");
    process::exit(1);
}

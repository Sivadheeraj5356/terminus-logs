//! Reference planner, swapped in for environment/main.rs at grading time. Rather than trust any one
//! design's short record, it fits a weighted straight line to the whole board's log clean-rate against
//! blend_grade, then sizes each design from a rate set a fixed number of prediction deviations below
//! that line. Whichever designs the record pins loosest take the steepest markdown, and it is that
//! markdown that keeps the weakest of them, and the joint floor riding on it, whole across a run that
//! has not been poured.

use std::env;
use std::fs;
use std::process;

const Z_PRED: f64 = 3.0;
// Sizing aims past the floor rather than at it: a fixed fraction of the distance from the floor up to
// 1 is folded in, so the shakiest design still holds margin next run. At 0.6 that fraction pushes a
// floor of 0.95 up to roughly 0.97 as the goal.
const FLOOR_HEADROOM: f64 = 0.6;

struct Candle {
    id: String,
    blend_grade: f64,
    cost_line: f64,
    cost_shop: f64,
    poured: i64,
    clean: i64,
}

struct Policy {
    reference_blend_grade: f64,
    rate_min: f64,
    rate_max: f64,
    burn_floor: f64,
    line_capacity: i64,
    cost_ceiling: f64,
}

/// The weighted least-squares line of log clean-rate on centered blend_grade, carrying the moment
/// sums it needs to return a prediction deviation for any design.
struct Fit {
    b0: f64,
    b1: f64,
    s2: f64,
    s1: f64,
    sx: f64,
    sxx: f64,
    det: f64,
    ref_grade: f64,
}

impl Fit {
    fn build(candles: &[Candle], ref_grade: f64) -> Fit {
        let n = candles.len();
        let mut delta = vec![0.0f64; n];
        let mut y = vec![0.0f64; n];
        let mut w = vec![0.0f64; n];
        let (mut s1, mut sx, mut sxx, mut sy, mut sxy) = (0.0, 0.0, 0.0, 0.0, 0.0);
        for (i, c) in candles.iter().enumerate() {
            let ph = (c.clean as f64 + 0.5) / (c.poured as f64 + 1.0);
            delta[i] = c.blend_grade - ref_grade;
            y[i] = ph.ln();
            w[i] = c.poured as f64 * ph * (1.0 - ph);
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
        for i in 0..n {
            let r = y[i] - (b0 + b1 * delta[i]);
            wr2 += w[i] * r * r;
        }
        let s2 = wr2 / s1 * n as f64 / (n as f64 - 2.0);
        Fit { b0, b1, s2, s1, sx, sxx, det, ref_grade }
    }

    /// Reads the design off the fitted line, walks it down Z_PRED prediction deviations, and keeps it
    /// inside the band. Where a record is empty or all faults the design draws zero weight in the fit,
    /// so its count rests wholly on this lowered line, never on the odd clean burn its log happens to hold.
    fn lower_rate(&self, c: &Candle, lo: f64, hi: f64) -> f64 {
        let d = c.blend_grade - self.ref_grade;
        let v_mean = (self.sxx - 2.0 * d * self.sx + d * d * self.s1) / self.det;
        let sd = (v_mean + self.s2).max(0.0).sqrt();
        let theta = (self.b0 + self.b1 * d - Z_PRED * sd).exp();
        clamp(theta, lo, hi)
    }
}

fn main() {
    let dir = env::args().nth(1).unwrap_or_else(|| "data".to_string());

    let mut candles = load_candles(&format!("{dir}/designs.csv"));
    fold_log(&format!("{dir}/burn_log.csv"), &mut candles);
    let pol = read_policy(&format!("{dir}/run_program.json"));

    let fit = Fit::build(&candles, pol.reference_blend_grade);
    let rates: Vec<f64> = candles.iter().map(|c| fit.lower_rate(c, pol.rate_min, pol.rate_max)).collect();

    let target = 1.0 - (1.0 - pol.burn_floor) * FLOOR_HEADROOM;
    let counts: Vec<i64> = rates.iter().map(|&p| candles_for(p, target)).collect();
    let plan = split_routes(&candles, &counts, pol.line_capacity);

    guard_policy(&plan, &candles, &rates, &counts, &pol);

    println!("{}", emit(&plan));
}

/// Will not return a plan that crosses either limit. No design's clean-burn chance at its sizing rate
/// may fall under the floor, and the line and shop bill together has to land below the ceiling.
fn guard_policy(plan: &[Row], candles: &[Candle], rates: &[f64], counts: &[i64], pol: &Policy) {
    for i in 0..candles.len() {
        let chance = 1.0 - (1.0 - rates[i]).powi(counts[i] as i32);
        if chance < pol.burn_floor {
            die(&format!(
                "design {} under burn floor: {:.4} < {:.4}",
                candles[i].id, chance, pol.burn_floor
            ));
        }
    }
    let mut cost = 0.0;
    for (i, r) in plan.iter().enumerate() {
        cost += r.line_pours as f64 * candles[i].cost_line;
        cost += r.shop_pours as f64 * candles[i].cost_shop;
    }
    if cost > pol.cost_ceiling {
        die(&format!("committed cost {:.2} over ceiling {:.2}", cost, pol.cost_ceiling));
    }
}

fn candles_for(p: f64, target: f64) -> i64 {
    let p = clamp(p, 1e-6, 0.999999);
    ((1.0 - target).ln() / (1.0 - p).ln()).ceil() as i64
}

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
        cost_ceiling: num_field(&text, "cost_ceiling"),
    }
}

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

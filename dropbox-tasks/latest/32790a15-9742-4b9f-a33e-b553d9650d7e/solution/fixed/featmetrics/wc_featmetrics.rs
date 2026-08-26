use serde_json::Value;

pub fn round_score(value: f64, precision: i32) -> Value {
    let factor = 10f64.powi(precision);
    let rounded = (value * factor).round() / factor;
    if (rounded - rounded.round()).abs() < 1e-12 {
        Value::from(rounded as i64)
    } else {
        // keep as number
        Value::from(rounded)
    }
}

pub fn needs_review(score: &Value, min_sev: f64) -> bool {
    let v = score.as_f64().or_else(|| score.as_i64().map(|i| i as f64)).unwrap_or(0.0);
    v + 1e-12 < min_sev
}

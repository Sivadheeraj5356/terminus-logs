use crate::types::{CheckResult, Counterexample};
use crate::util::{hash_hex, json_string};
use std::collections::{BTreeMap, BTreeSet};
use std::fmt::Write as _;

pub fn render(model_hash: &str, results: &[CheckResult]) -> Vec<u8> {
    let state_text = state_text(model_hash, results);
    let state_hash = hash_hex(state_text.as_bytes());
    let mut out = String::from("{\"schema\":1,\"model_hash\":");
    out.push_str(&json_string(model_hash));
    out.push_str(",\"checks\":[");
    for (index, result) in results.iter().enumerate() {
        if index > 0 {
            out.push(',');
        }
        write_check(&mut out, result);
    }
    out.push_str("],\"state_hash\":");
    out.push_str(&json_string(&state_hash));
    out.push_str("}\n");
    out.into_bytes()
}

fn write_check(out: &mut String, result: &CheckResult) {
    out.push('{');
    out.push_str("\"session\":");
    out.push_str(&json_string(&result.state.session));
    out.push_str(",\"check\":");
    out.push_str(&json_string(&result.state.check));
    let _ = write!(out, ",\"budget\":{}", result.state.budget);
    out.push_str(",\"point\":");
    write_values(out, &result.state.point);
    out.push_str(",\"locked\":[");
    for (index, feature) in result.state.locked.iter().enumerate() {
        if index > 0 {
            out.push(',');
        }
        out.push_str(&json_string(feature));
    }
    out.push(']');
    out.push_str(",\"prediction\":");
    out.push_str(&json_string(result.base.prediction));
    let _ = write!(out, ",\"score\":{}", result.base.score);
    out.push_str(",\"result\":");
    match &result.counterexample {
        None => out.push_str("{\"kind\":\"certified\"}"),
        Some(counterexample) => write_counterexample(out, counterexample),
    }
    out.push('}');
}

fn write_counterexample(out: &mut String, counterexample: &Counterexample) {
    out.push_str("{\"kind\":\"counterexample\"");
    let _ = write!(
        out,
        ",\"cost\":{},\"changed\":{}",
        counterexample.cost, counterexample.changed
    );
    out.push_str(",\"values\":");
    write_values(out, &counterexample.values);
    out.push_str(",\"prediction\":");
    out.push_str(&json_string(counterexample.evaluation.prediction));
    let _ = write!(out, ",\"score\":{}", counterexample.evaluation.score);
    out.push_str(",\"votes\":[");
    for (index, vote) in counterexample.evaluation.votes.iter().enumerate() {
        if index > 0 {
            out.push(',');
        }
        out.push_str("{\"tree\":");
        out.push_str(&json_string(&vote.tree));
        let _ = write!(out, ",\"leaf\":{},\"vote\":{}}}", vote.leaf, vote.vote);
    }
    out.push_str("]}");
}

fn write_values(out: &mut String, values: &BTreeMap<String, i32>) {
    out.push('[');
    for (index, (feature, value)) in values.iter().enumerate() {
        if index > 0 {
            out.push(',');
        }
        out.push_str("{\"feature\":");
        out.push_str(&json_string(feature));
        let _ = write!(out, ",\"value\":{value}}}");
    }
    out.push(']');
}

fn state_text(model_hash: &str, results: &[CheckResult]) -> String {
    let mut out = format!("MODEL|{model_hash}\n");
    for result in results {
        let locked = set_csv(&result.state.locked);
        let point = values_csv(&result.state.point);
        let kind = if result.counterexample.is_some() { "counterexample" } else { "certified" };
        let _ = writeln!(
            out,
            "CHECK|{}|{}|{}|{}|{}|{}|{}|{}",
            result.state.session,
            result.state.check,
            result.state.budget,
            result.base.prediction,
            result.base.score,
            locked,
            point,
            kind
        );
        let _ = &result.counterexample;
    }
    out
}

fn values_csv(values: &BTreeMap<String, i32>) -> String {
    values
        .iter()
        .map(|(feature, value)| format!("{feature}={value}"))
        .collect::<Vec<_>>()
        .join(",")
}

fn set_csv(values: &BTreeSet<String>) -> String {
    values.iter().cloned().collect::<Vec<_>>().join(",")
}


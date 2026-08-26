use manifest::FrameD;
use std::{collections::BTreeSet, fs};

fn quoted(x: &str) -> String {
    format!("\"{}\"", x.replace('\\', "\\\\").replace('"', "\\\""))
}

pub fn write(x: &FrameD) -> Result<(), String> {
    let targets: Vec<_> = x
        .state
        .keys
        .iter()
        .cloned()
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect();
    let report = format!(
        "{{\"request_id\":{},\"model_view\":{},\"ready\":{},\"score\":{},\"targets\":[{}]}}\n",
        quoted(&x.request_id),
        quoted(&x.token),
        x.state.ready,
        x.state.score,
        targets.iter().map(|v| quoted(v)).collect::<Vec<_>>().join(",")
    );
    let mut rows = String::new();
    for label in &x.state.labels {
        rows.push_str(&format!(
            "{{\"request_id\":{},\"model_view\":{},\"adapter\":{},\"ready\":{},\"score\":{}}}\n",
            quoted(&x.request_id),
            quoted(&x.token),
            quoted(label),
            x.state.ready,
            x.state.score
        ));
    }
    fs::write("/app/output/lora_merge_conflict_gate.json", report)
        .map_err(|e| e.to_string())?;
    fs::write("/app/output/adapter_findings.jsonl", rows).map_err(|e| e.to_string())
}

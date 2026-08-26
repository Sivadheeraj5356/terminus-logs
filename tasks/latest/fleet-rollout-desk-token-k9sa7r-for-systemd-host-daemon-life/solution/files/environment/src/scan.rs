use std::collections::HashMap;
use std::fs;
use std::path::Path;

#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct ScenarioInput {
    pub scenario: u32,
    pub issue: u64,
    pub sig: u64,
    pub source: String,
    pub target: String,
    pub stage: u64,
    pub anchor: u64,
    pub settle: u64,
    pub tail: u64,
    pub rank_a: u64,
    pub rank_b: u64,
    pub epoch: u64,
}

fn kv(path: &Path) -> HashMap<String, String> {
    let mut map = HashMap::new();
    let text = fs::read_to_string(path).unwrap_or_default();
    for raw in text.lines() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        for item in line.split_whitespace() {
            if let Some((k, v)) = item.split_once('=') {
                map.insert(k.to_string(), v.to_string());
            }
        }
    }
    map
}

fn num(map: &HashMap<String, String>, key: &str) -> u64 {
    map.get(key).and_then(|v| v.parse().ok()).unwrap_or(0)
}

fn text(map: &HashMap<String, String>, key: &str, fallback: &str) -> String {
    map.get(key).cloned().unwrap_or_else(|| fallback.to_string())
}

pub fn parse_root(root: &str, scenario_id: u32) -> ScenarioInput {
    let base = Path::new(root);
    let xfer = kv(&base.join("a0.evt"));
    let ledger = kv(&base.join("b0.evt"));
    let res = kv(&base.join("p0.res"));
    ScenarioInput {
        scenario: scenario_id,
        issue: num(&xfer, "issue"),
        sig: num(&xfer, "sig"),
        source: text(&xfer, "source", "na"),
        target: text(&xfer, "target", "na"),
        stage: num(&ledger, "stage"),
        anchor: num(&ledger, "anchor"),
        settle: num(&ledger, "settle"),
        tail: num(&res, "tail"),
        rank_a: num(&res, "rank_a"),
        rank_b: num(&res, "rank_b"),
        epoch: num(&res, "epoch"),
    }
}

pub fn case_root(scenario_id: u32) -> String {
    format!("/app/cases/seq/s{scenario_id}")
}

pub fn parse(scenario_id: u32) -> ScenarioInput {
    parse_root(&case_root(scenario_id), scenario_id)
}

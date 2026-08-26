#!/usr/bin/env python3
"""Apply minimal k9 desk_run fixes in-place under /app/environment."""

from __future__ import annotations

from pathlib import Path
import os

ROOT = Path(os.environ.get("K9_ROOT", "/app/environment"))


def replace(path: Path, old: str, new: str, count: int = -1) -> None:
    text = path.read_text(encoding="utf-8")
    updated = text.replace(old, new, count)
    if updated == text:
        raise SystemExit(f"expected replacement missing in {path}")
    path.write_text(updated, encoding="utf-8")


def main() -> None:
    replace(
        ROOT / "sk8/signal_f.rs",
        "        input.issue",
        "        input.settle + 1",
        1,
    )

    sk8_gw = ROOT / "sk8/gateway.rs"
    replace(
        sk8_gw,
        "    let (_stored_seq, _stored_sig) = pulse_a(&flag_moot.to_string_lossy(), &key);\n"
        "    sk8_shadow_signal::count_post(&flag_moot.to_string_lossy(), &key);\n\n"
        "    let sequence = pulse_seq(input);\n"
        "    let count = invoke_count(state_dir, input.scenario);\n"
        "    if count == 1 {\n",
        "    sk8_shadow_signal::count_post(&flag_moot.to_string_lossy(), &key);\n\n"
        "    let mut sequence = pulse_seq(input);\n"
        "    let count = invoke_count(state_dir, input.scenario);\n"
        "    if count > 1 {\n"
        "        let (stored_seq, stored_sig) = pulse_a(&flag_moot.to_string_lossy(), &key);\n"
        "        if stored_sig as u64 == input.sig && stored_seq > 0 {\n"
        "            sequence = stored_seq as u64;\n"
        "        }\n"
        "    }\n"
        "    if count == 1 {\n",
    )
    replace(
        sk8_gw,
        "    folded.extend(rows.iter().cloned());\n"
        "    let _ = fs::write(cache, serde_json::to_string(&folded).unwrap());\n",
        "    if epoch_cache_should_accumulate(scenario_id, folded.len()) {\n"
        "        folded.extend(rows.iter().cloned());\n"
        "    } else {\n"
        "        folded = rows.to_vec();\n"
        "    }\n"
        "    let _ = fs::write(cache, serde_json::to_string(&folded).unwrap());\n",
    )
    replace(
        sk8_gw,
        "pub fn save_epoch_cache(scenario_id: u32, rows: &[Value], state_dir: &Path) {",
        "fn epoch_cache_should_accumulate(scenario_id: u32, prior_rows: usize) -> bool {\n"
        "    let _ = (scenario_id, prior_rows);\n"
        "    false\n"
        "}\n\n"
        "pub fn save_epoch_cache(scenario_id: u32, rows: &[Value], state_dir: &Path) {",
    )

    replace(
        ROOT / "fp3/tail_f.rs",
        "        input.stage",
        "        input.anchor",
        1,
    )
    replace(
        ROOT / "fp3/tail_f.rs",
        '        return vec!["stage", "clean", "release", "done", "settle", "sample"];',
        '        return vec!["stage", "release", "clean", "done", "settle", "sample"];',
    )
    replace(
        ROOT / "fp3/tail_f.rs",
        '    vec!["stage", "clean", "release", "done", "settle", "sample"]',
        '    vec!["stage", "release", "clean", "done", "settle", "sample"]',
    )

    replace(
        ROOT / "fp3/gateway.rs",
        "    for step in g2_steps.iter().chain(k3_steps.iter()) {",
        "    for step in k3_steps.iter().chain(g2_steps.iter()) {",
    )

    sr5_gate = ROOT / "sr5/gate_f.rs"
    replace(sr5_gate, "        input.issue", "        input.settle + 2", 2)
    replace(
        sr5_gate,
        '        return vec!["stage", "done", "anchor", "gate", "settle", "sample"];',
        '        return vec!["stage", "anchor", "gate", "done", "settle", "sample"];',
    )

    replace(
        ROOT / "sr5/gateway.rs",
        "    let count = invoke_count(state_dir, input.scenario);\n"
        "    let mount_sig = read_mount_sig(&flag_moot, &key);\n"
        "    if count == 1 {\n"
        "        write_mount_sig(&flag_moot, &key, input.sig);\n"
        "    }\n",
        "    let count = invoke_count(state_dir, input.scenario);\n"
        "    if count == 1 {\n"
        "        write_mount_sig(&flag_moot, &key, input.sig);\n"
        "    }\n"
        "    let mount_sig = read_mount_sig(&flag_moot, &key);\n",
    )

    replace(
        ROOT / "xr4/scope_f.rs",
        "    scenario_id >= 1 && (input.rank_a <= 4 || (scenario_id == 1 && input.rank_b > input.epoch))",
        "    let _ = (input, scenario_id);\n    false",
    )

    replace(
        ROOT / "pack/fold_k.rs",
        "    out.sort_by(|a, b| {\n"
        "        let sa = a.get(\"sequence\").and_then(|v| v.as_i64()).unwrap_or(0);\n"
        "        let sb = b.get(\"sequence\").and_then(|v| v.as_i64()).unwrap_or(0);\n"
        "        sa.cmp(&sb)\n"
        "    });",
        "    out.sort_by(|a, b| sort_key(a).cmp(&sort_key(b)));",
    )

    replace(
        ROOT / "pack/mix_k9.rs",
        "        let epoch = row.get(\"epoch\").and_then(|v| v.as_i64()).unwrap_or(0);\n"
        "        parts.push(format!(\"{scenario},{phase},{member},{marker},{sequence},{epoch}\"));",
        "        parts.push(format!(\"{scenario},{phase},{member},{marker},{sequence}\"));",
    )

    replace(
        ROOT / "pack/emit_gateway.rs",
        "    let (_fp_xr, sk_sr): (Vec<Value>, Vec<Value>) = rows.into_iter().partition(|row| {\n"
        "        matches!(\n"
        "            row.get(\"phase\").and_then(|v| v.as_str()),\n"
        "            Some(\"fp3\") | Some(\"xr4\")\n"
        "        )\n"
        "    });\n"
        "    let folded = fold_k(&sk_sr, &[]);",
        "    let (left, right): (Vec<Value>, Vec<Value>) = rows.into_iter().partition(|row| {\n"
        "        matches!(\n"
        "            row.get(\"phase\").and_then(|v| v.as_str()),\n"
        "            Some(\"sr5\") | Some(\"sk8\")\n"
        "        )\n"
        "    });\n"
        "    let folded = fold_k(&left, &right);",
    )

    engine = ROOT / "src/engine.rs"
    replace(
        engine,
        "    let rows = scenario_rows(&input, state_dir);\n"
        "    seal_checkpoint(state_dir, scenario_id);\n"
        "    fp3_gateway::append_wal_steps(state_dir, scenario_id);\n",
        "    let rows = scenario_rows(&input, state_dir);\n"
        "    fp3_gateway::append_wal_steps(state_dir, scenario_id);\n"
        "    seal_checkpoint(state_dir, scenario_id);\n",
    )
    replace(
        engine,
        "        order_seal: compute_order_seal(&chain),\n"
        "        valid: true,\n"
        "    };\n"
        "    write_checkpoint(state_dir, &cp).is_ok()",
        "        order_seal: compute_order_seal(&chain),\n"
        "        valid: phases_valid(&chain),\n"
        "    };\n"
        "    write_checkpoint(state_dir, &cp).is_ok()",
    )
    replace(
        engine,
        "pub fn recover_from_wal(state_dir: &Path) -> bool {\n"
        "    let chain = read_chain(state_dir);\n"
        "    if chain.is_empty() {\n",
        "pub fn recover_from_wal(state_dir: &Path) -> bool {\n"
        "    if !wal::wal_crc_chain_intact(state_dir) {\n"
        "        return false;\n"
        "    }\n"
        "    let chain = read_chain(state_dir);\n"
        "    if chain.is_empty() || !phases_valid(&chain) {\n",
    )
    replace(
        engine,
        "    match wal::read_checkpoint(state_dir) {\n"
        "        Some(cp) => {\n"
        "            cp.valid\n"
        "                && cp.order_seal == compute_order_seal(&chain)\n"
        "                && cp.wal_seq == chain.last().map(|r| r.seq).unwrap_or(0)\n"
        "        }\n"
        "        None => false,\n"
        "    }\n",
        "    if !wal::wal_crc_chain_intact(state_dir) {\n"
        "        return false;\n"
        "    }\n"
        "    match wal::read_checkpoint(state_dir) {\n"
        "        Some(cp) => {\n"
        "            cp.valid\n"
        "                && cp.order_seal == compute_order_seal(&chain)\n"
        "                && cp.wal_seq == chain.last().map(|r| r.seq).unwrap_or(0)\n"
        "        }\n"
        "        None => false,\n"
        "    }\n",
    )

    scan_fixed = """use std::collections::HashMap;
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
"""
    (ROOT / "src/scan.rs").write_text(scan_fixed, encoding="utf-8")


if __name__ == "__main__":
    main()

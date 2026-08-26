#!/usr/bin/env bash
set -euo pipefail

cd /app/environment

python3 - <<'PY'
from pathlib import Path

root = Path("/app/environment")

p = root / "src/ingest/parse.rs"
text = p.read_text()
text = text.replace(
    "let rotate_gen = u32::from_be_bytes(data[4..8].try_into().unwrap());",
    "let rotate_gen = u32::from_le_bytes(data[4..8].try_into().unwrap());",
)
p.write_text(text)

p = root / "src/cutoff/boundary.rs"
p.write_text(
    "pub fn journal_included(rotate_gen: u32, bound_rotate: u32, slack: u32) -> bool {\n"
    "    rotate_gen <= bound_rotate + slack\n"
    "}\n"
)

p = root / "src/align/segment.rs"
text = p.read_text()
text = text.replace(
    "let start = (rec.ts_ms / w) * w + 1;",
    "let start = (rec.ts_ms / w) * w;",
)
p.write_text(text)

p = root / "src/combine/stats.rs"
p.write_text(
    """use std::collections::BTreeMap;

use crate::types::{ScopeRecord, WindowRow};

pub fn rollup_windows(buckets: BTreeMap<u64, Vec<ScopeRecord>>) -> Vec<WindowRow> {
    let mut out = Vec::new();
    let mut prev_last_seq: Option<u32> = None;
    for (start, mut recs) in buckets {
        recs.sort_by_key(|r| r.ts_ms);
        let mut sum: i64 = 0;
        let mut min_v: i32 = 0;
        let mut max_v: i32 = 0;
        let mut gap_sum: u32 = 0;
        for (i, rec) in recs.iter().enumerate() {
            sum += rec.size_delta as i64;
            if i == 0 {
                min_v = rec.size_delta;
                max_v = rec.size_delta;
                if let Some(prev) = prev_last_seq {
                    let cross = rec.seq_num.saturating_sub(prev).saturating_sub(1);
                    gap_sum += cross;
                }
            } else {
                if rec.size_delta < min_v {
                    min_v = rec.size_delta;
                }
                if rec.size_delta > max_v {
                    max_v = rec.size_delta;
                }
                let gap = rec.seq_num.saturating_sub(recs[i - 1].seq_num).saturating_sub(1);
                gap_sum += gap;
            }
        }
        if let Some(last) = recs.last() {
            prev_last_seq = Some(last.seq_num);
        }
        out.push(WindowRow {
            start_ms: start,
            count: recs.len() as u32,
            size_delta_sum: sum,
            size_min: min_v,
            size_max: max_v,
            seq_gap_sum: gap_sum,
        });
    }
    out
}
"""
)

p = root / "src/policy/filter.rs"
p.write_text(
    "pub const PRESERVE: u32 = 0x8000_0000;\n\n"
    "pub fn record_allowed(action_mask: u32, effective_mask: u32) -> bool {\n"
    "    let stripped = action_mask & !PRESERVE;\n"
    "    (stripped & effective_mask) != 0\n"
    "}\n"
)

p = root / "src/ingest/cache.rs"
p.write_text(
    """use std::fs;
use std::path::Path;

use crate::types::Manifest;

#[derive(Debug, Clone, serde::Deserialize)]
struct CacheRow {
    profile: String,
    width_ms: u64,
    manifest_gen: u32,
}

pub fn resolve_width(profile: &str, manifest: &Manifest) -> u64 {
    let path = Path::new("/app/environment/ops/sweep.cache");
    let raw = fs::read_to_string(path).unwrap_or_else(|_| "[]".into());
    let rows: Vec<CacheRow> = serde_json::from_str(&raw).unwrap_or_default();
    for row in rows {
        if row.profile == profile && row.manifest_gen >= manifest.manifest_gen {
            return row.width_ms;
        }
    }
    manifest.window_width_ms
}
"""
)

p = root / "src/main.rs"
p.write_text(
    """use std::env;
use std::fs;
use std::path::PathBuf;

use volsweep::export::{emit, state};
use volsweep::ingest::{cache, parse};
use volsweep::consolidate;
use volsweep::policy;
use volsweep::types::{ProbeSnapshot, ScopeRecord, SweepLedger};
use volsweep::{align, combine, cutoff};

const APP_ROOT: &str = "/app/environment";

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 3 {
        eprintln!("usage: volsweep <rebuild|merge|probe> <profile>");
        std::process::exit(2);
    }
    let workflow = args[1].as_str();
    let profile = args[2].as_str();

    match workflow {
        "rebuild" => run_rebuild(profile),
        "merge" => run_merge(profile),
        "probe" => run_probe(profile),
        _ => {
            eprintln!("unknown workflow");
            std::process::exit(2);
        }
    }
}

fn fixture_dir(profile: &str) -> PathBuf {
    PathBuf::from(APP_ROOT).join("fixtures").join(profile)
}

fn manifest_path(profile: &str) -> PathBuf {
    PathBuf::from(APP_ROOT)
        .join("ops/manifests")
        .join(format!("{profile}.json"))
}

fn to_scope_record(rotate_gen: u32, journal_file: &str, rec: &parse::ParsedRecord) -> ScopeRecord {
    ScopeRecord {
        rotate_gen,
        scope_id: rec.scope_id,
        action_mask: rec.action_mask,
        size_delta: rec.size_delta,
        seq_num: rec.seq_num,
        ts_ms: rec.ts_ms,
        rel_path: rec.rel_path.clone(),
        payload: rec.payload.clone(),
        journal_file: journal_file.to_string(),
    }
}

fn run_rebuild(profile: &str) {
    let manifest = parse::load_manifest(&manifest_path(profile));
    let effective = policy::effective_mask(profile, manifest.sweep_mask);
    let journal = fixture_dir(profile).join(format!("{}.vsw1", profile.replace("site-", "")));
    let parsed = parse::read_journal(&journal);
    let bound = manifest.bound_rotate;
    let slack = manifest.slack;

    let mut included = Vec::new();
    let mut dropped = 0u32;
    if cutoff::journal_included(parsed.header.rotate_gen, bound, slack) {
        for rec in parsed.records {
            if policy::record_allowed(rec.action_mask, effective) {
                included.push(to_scope_record(parsed.header.rotate_gen, "", &rec));
            } else {
                dropped += 1;
            }
        }
    } else {
        dropped = parsed.records.len() as u32;
    }

    let width = cache::resolve_width(profile, &manifest);
    let windows = align::segment_by_time(&included, width);
    let stats_windows = combine::rollup_windows(windows);
    let payloads: Vec<Vec<u8>> = included.iter().map(|r| r.payload.clone()).collect();
    let digest = emit::records_digest(&payloads);
    let reg = SweepLedger {
        profile: profile.to_string(),
        workflow: "rebuild".into(),
        included_records: included.len() as u32,
        dropped_records: dropped,
        windows: stats_windows,
        rebuild_digest: Some(format!("{:016x}", digest)),
        merge_digest: None,
    };
    emit::write_ledger(&reg);
    state::write_scope_state(profile, &manifest, &included, bound);
}

fn run_merge(profile: &str) {
    let manifest = parse::load_manifest(&manifest_path(profile));
    let effective = policy::effective_mask(profile, manifest.sweep_mask);
    let dir = fixture_dir(profile);
    let mut paths: Vec<PathBuf> = fs::read_dir(&dir)
        .unwrap()
        .filter_map(|e| e.ok())
        .map(|e| e.path())
        .filter(|p| p.extension().map(|x| x == "vsw1").unwrap_or(false))
        .collect();
    paths.sort();

    let mut journals = Vec::new();
    for p in &paths {
        journals.push((p.clone(), parse::read_journal(p)));
    }
    let bound = journals.last().map(|(_, j)| j.header.bound_rotate).unwrap_or(0);

    let mut included = Vec::new();
    let mut dropped = 0u32;
    for (path, parsed) in &journals {
        let journal_file = path
            .file_name()
            .map(|name| name.to_string_lossy().into_owned())
            .unwrap_or_default();
        if cutoff::journal_included(parsed.header.rotate_gen, bound, parsed.header.slack) {
            for rec in &parsed.records {
                if policy::record_allowed(rec.action_mask, effective) {
                    included.push(to_scope_record(
                        parsed.header.rotate_gen,
                        &journal_file,
                        rec,
                    ));
                } else {
                    dropped += 1;
                }
            }
        } else {
            dropped += parsed.records.len() as u32;
        }
    }

    let merged = consolidate::consolidate_records(included);
    let width = cache::resolve_width(profile, &manifest);
    let windows = align::segment_by_time(&merged, width);
    let stats_windows = combine::rollup_windows(windows);
    let payloads: Vec<Vec<u8>> = merged.iter().map(|r| r.payload.clone()).collect();
    let digest = emit::records_digest(&payloads);
    let reg = SweepLedger {
        profile: profile.to_string(),
        workflow: "merge".into(),
        included_records: merged.len() as u32,
        dropped_records: dropped,
        windows: stats_windows,
        rebuild_digest: None,
        merge_digest: Some(format!("{:016x}", digest)),
    };
    emit::write_ledger(&reg);
    state::write_scope_state(profile, &manifest, &merged, bound);
}

fn run_probe(profile: &str) {
    let manifest = parse::load_manifest(&manifest_path(profile));
    let width = cache::resolve_width(profile, &manifest);
    let snap = ProbeSnapshot {
        profile: profile.to_string(),
        effective_mask: policy::effective_mask(profile, manifest.sweep_mask),
        cache_width_ms: width,
        manifest_gen: manifest.manifest_gen,
    };
    emit::write_probe(&snap);
}
"""
)

p = root / "src/export/state.rs"
p.write_text(
    """use std::fs;
use std::path::Path;

use crate::types::{Manifest, ScopeRecord, ScopeState};

pub fn write_scope_state(
    _profile: &str,
    manifest: &Manifest,
    records: &[ScopeRecord],
    _bound_rotate: u32,
) {
    let last = records.iter().map(|r| r.rotate_gen).max().unwrap_or(0);
    let state = ScopeState {
        manifest_gen: manifest.manifest_gen,
        scope_count: records.len() as u32,
        last_rotate_gen: last,
    };
    let dir = Path::new("/app/state");
    fs::create_dir_all(dir).ok();
    let json = serde_json::to_string_pretty(&state).expect("state json");
    fs::write(dir.join("scope_state.json"), json).expect("write state");
}
"""
)

p = root / "src/consolidate/dedup.rs"
p.write_text(
    """use std::collections::HashMap;

use crate::types::ScopeRecord;

pub fn consolidate_records(records: Vec<ScopeRecord>) -> Vec<ScopeRecord> {
    let mut best: HashMap<(u32, u32), ScopeRecord> = HashMap::new();
    let mut order: Vec<(u32, u32)> = Vec::new();
    for rec in records {
        let key = (rec.scope_id, rec.action_mask);
        match best.get(&key) {
            None => {
                order.push(key);
                best.insert(key, rec);
            }
            Some(cur) => {
                if rec.rotate_gen > cur.rotate_gen {
                    best.insert(key, rec);
                } else if rec.rotate_gen == cur.rotate_gen && rec.journal_file > cur.journal_file {
                    best.insert(key, rec);
                }
            }
        }
    }
    order.into_iter().map(|key| best.remove(&key).unwrap()).collect()
}
"""
)
PY

cargo build --release

/app/environment/target/release/volsweep rebuild site-alpha
/app/environment/target/release/volsweep merge site-beta

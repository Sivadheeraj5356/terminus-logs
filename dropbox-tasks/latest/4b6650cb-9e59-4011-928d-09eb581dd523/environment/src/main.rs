use std::env;
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
    let journal = fixture_dir(profile).join(format!("{}.vsw1", profile.replace("site-", "")));
    let parsed = parse::read_journal(&journal);
    let bound = manifest.bound_rotate;
    let slack = manifest.slack;

    let mut included = Vec::new();
    let mut dropped = 0u32;
    if cutoff::journal_included(parsed.header.rotate_gen, bound, slack) {
        for rec in parsed.records {
            if policy::record_allowed(rec.action_mask, manifest.sweep_mask) {
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
    let digest = emit::records_digest(&included.iter().map(|r| r.payload.clone()).collect::<Vec<_>>());
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
    let slack = manifest.slack;

    let mut included = Vec::new();
    let mut dropped = 0u32;
    for (path, parsed) in &journals {
        let journal_file = path
            .file_name()
            .map(|name| name.to_string_lossy().into_owned())
            .unwrap_or_default();
        if cutoff::journal_included(parsed.header.rotate_gen, bound, slack) {
            for rec in &parsed.records {
                if policy::record_allowed(rec.action_mask, manifest.sweep_mask) {
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
        effective_mask: manifest.sweep_mask,
        cache_width_ms: width,
        manifest_gen: manifest.manifest_gen,
    };
    emit::write_probe(&snap);
}

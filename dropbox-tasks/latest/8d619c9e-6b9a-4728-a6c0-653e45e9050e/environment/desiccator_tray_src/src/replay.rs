use std::collections::{BTreeMap, HashMap, HashSet};
use std::fs;
use std::path::PathBuf;

use crate::ops::apply_event;
use crate::parse::parse_line;
use crate::types::{ReplayResult, TrayCfg, TrayState};

pub fn replay_shards(
    cfg: &HashMap<String, TrayCfg>,
    shards: &[PathBuf],
) -> Result<ReplayResult, i32> {
    let mut trays = BTreeMap::new();
    for (name, tc) in cfg.iter() {
        trays.insert(
            name.clone(),
            TrayState {
                name: name.clone(),
                capacity_units: tc.capacity_units,
                tier: tc.tier,
                regen_every: tc.regen_every,
                ..TrayState::default()
            },
        );
    }
    let mut accepted = HashSet::new();
    let mut rejected = Vec::new();
    let mut duplicates = Vec::new();
    let mut invalid = Vec::new();
    let mut ordinal = 0usize;
    let mut applied = 0usize;
    let mut loads_applied = 0i64;
    let mut unloads_applied = 0i64;

    for shard in shards {
        let bytes = fs::read(shard).map_err(|_| 1)?;
        let text = String::from_utf8(bytes).map_err(|_| 1)?;
        let source = shard.to_string_lossy().to_string();
        let mut lines: Vec<(usize, String)> = Vec::new();
        for (idx, raw) in text.split('\n').enumerate() {
            let line = raw.trim_end_matches('\r');
            if line.trim().is_empty() {
                continue;
            }
            lines.push((idx + 1, line.to_string()));
        }
        lines.sort_by(|a, b| a.1.cmp(&b.1));
        for (line_no, line) in lines {
            let cur = ordinal;
            ordinal += 1;
            match parse_line(&line) {
                Err(()) => invalid.push(cur),
                Ok(parsed) => {
                    let op = parsed.op.clone();
                    match apply_event(&mut trays, cfg, &parsed, &accepted) {
                        Ok(()) => {
                            applied += 1;
                            if op == "LOAD" {
                                loads_applied += 1;
                            }
                            if op == "UNLOAD" {
                                unloads_applied += 1;
                            }
                        }
                        Err(reason) => {
                            accepted.insert(parsed.event_id.clone());
                            rejected.push((
                                cur,
                                parsed.event_id.clone(),
                                reason.clone(),
                                source.clone(),
                                line_no,
                            ));
                            if reason == "DUPLICATE_EVENT" {
                                duplicates.push((cur, parsed.event_id.clone(), reason));
                            }
                        }
                    }
                }
            }
        }
    }

    Ok(ReplayResult {
        trays,
        tray_cfg: cfg.clone(),
        rejected,
        duplicates,
        invalid,
        total_lines: ordinal,
        applied,
        loads_applied,
        unloads_applied,
    })
}

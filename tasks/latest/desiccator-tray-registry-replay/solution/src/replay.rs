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
        let normalized = text.replace("\r\n", "\n").replace('\r', "\n");
        let source = shard.to_string_lossy().to_string();
        for (idx, raw) in normalized.split('\n').enumerate() {
            if raw.trim().is_empty() {
                continue;
            }
            let cur = ordinal;
            ordinal += 1;
            let line_no = idx + 1;
            match parse_line(raw) {
                Err(()) => invalid.push(cur),
                Ok(parsed) => {
                    let op = parsed.op.clone();
                    match apply_event(&mut trays, cfg, &parsed, &accepted) {
                        Ok(()) => {
                            accepted.insert(parsed.event_id.clone());
                            applied += 1;
                            if op == "LOAD" {
                                loads_applied += 1;
                            }
                            if op == "UNLOAD" {
                                unloads_applied += 1;
                            }
                        }
                        Err(reason) => {
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

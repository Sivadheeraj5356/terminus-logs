use super::cycle::resume_from_vault;
use super::sched::{RunMode, SchedulePlan, TrainingPlan};
use crate::q_in::PendingLane;
use crate::q_st::{load_vault, seal_v, Store, WalTail};
use crate::q_st::write_manifest;
use crate::q_rd::{acct, emit_gauge, fold_u, AccBuf, StepPhase};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

#[derive(Serialize, Deserialize)]
struct TraceRow {
    seq: i64,
    slot: i32,
    phase: String,
    tag: u64,
    payload_fp: String,
    step_index: u32,
}

struct TraceSink {
    path: PathBuf,
    rows: Vec<TraceRow>,
}

impl TraceSink {
    fn open(out: &Path) -> Result<Self, String> {
        fs::create_dir_all(out).map_err(|e| e.to_string())?;
        let path = out.join("run_trace.jsonl");
        let mut rows = Vec::new();
        if path.exists() {
            let body = fs::read_to_string(&path).map_err(|e| e.to_string())?;
            for line in body.lines() {
                if line.trim().is_empty() {
                    continue;
                }
                let row: TraceRow = serde_json::from_str(line).map_err(|e| e.to_string())?;
                rows.push(row);
            }
        }
        Ok(Self { path, rows })
    }

    fn max_seq(&self) -> i64 {
        self.rows.iter().map(|row| row.seq).max().unwrap_or(0)
    }

    fn admit_count(&self) -> u64 {
        self.rows
            .iter()
            .filter(|row| row.phase == "admit")
            .count() as u64
    }

    fn write_admit(
        &mut self,
        seq: i64,
        slot: u32,
        tag: u64,
        fp: &str,
        step_index: u32,
    ) -> Result<(), String> {
        self.push(seq, slot, "admit", tag, fp, step_index)
    }

    fn write_fold(
        &mut self,
        seq: i64,
        slot: u32,
        tag: u64,
        fp: &str,
        step_index: u32,
    ) -> Result<(), String> {
        self.push(seq, slot, "fold", tag, fp, step_index)
    }

    fn write_seal(
        &mut self,
        seq: i64,
        slot: u32,
        tag: u64,
        fp: &str,
        step_index: u32,
    ) -> Result<(), String> {
        self.push(seq, slot, "seal", tag, fp, step_index)
    }

    fn write_step(
        &mut self,
        seq: i64,
        slot: u32,
        tag: u64,
        fp: &str,
        step_index: u32,
    ) -> Result<(), String> {
        self.push(seq, slot, "step", tag, fp, step_index)
    }

    fn push(
        &mut self,
        seq: i64,
        slot: u32,
        phase: &str,
        tag: u64,
        fp: &str,
        step_index: u32,
    ) -> Result<(), String> {
        self.rows.push(TraceRow {
            seq,
            slot: slot as i32,
            phase: phase.to_string(),
            tag,
            payload_fp: fp.to_string(),
            step_index,
        });
        Ok(())
    }

    fn flush(&self) -> Result<(), String> {
        let mut file = fs::File::create(&self.path).map_err(|e| e.to_string())?;
        for row in &self.rows {
            let line = serde_json::to_string(row).map_err(|e| e.to_string())?;
            writeln!(file, "{line}").map_err(|e| e.to_string())?;
        }
        Ok(())
    }
}

fn payload_fp(values: &[f32]) -> String {
    let mut bytes = Vec::with_capacity(values.len() * 4);
    for value in values {
        bytes.extend_from_slice(&value.to_le_bytes());
    }
    format!("{:x}", Sha256::digest(&bytes))[..16].to_string()
}

fn step_fp(step_index: u32, tags: &[u64], _mode: &str) -> String {
    let csv = tags
        .iter()
        .map(|tag| tag.to_string())
        .collect::<Vec<_>>()
        .join(",");
    let payload = format!("step:{step_index};tags:{csv}");
    let hash = Sha256::digest(payload.as_bytes());
    format!("{:x}", hash)[..16].to_string()
}

fn acc_checksum(values: &[f32]) -> String {
    let bytes: Vec<u8> = values.iter().flat_map(|v| v.to_le_bytes()).collect();
    format!("{:x}", Sha256::digest(&bytes))[..16].to_string()
}

#[derive(Serialize)]
struct PassRecord {
    step_digest: String,
    balance_tally: i64,
    pending_slots: Vec<i32>,
    mode: String,
    acc_checksum: String,
}

fn next_pass_index(out: &Path) -> u32 {
    let dir = out.join("pass_transcripts");
    if !dir.exists() {
        return 0;
    }
    let mut max_idx = 0u32;
    if let Ok(entries) = fs::read_dir(&dir) {
        for entry in entries.flatten() {
            let name = entry.file_name();
            let name = name.to_string_lossy();
            if let Some(suffix) = name.strip_prefix("pass_").and_then(|s| s.strip_suffix(".json")) {
                if let Ok(idx) = suffix.parse::<u32>() {
                    max_idx = max_idx.max(idx + 1);
                }
            }
        }
    }
    max_idx
}

fn write_pass(
    out: &Path,
    pass_index: u32,
    step_fp: &str,
    tally: i64,
    pending: &[i32],
    mode: &str,
    acc: &[f32],
) -> Result<(), String> {
    let dir = out.join("pass_transcripts");
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let record = PassRecord {
        step_digest: step_fp.to_string(),
        balance_tally: tally,
        pending_slots: pending.to_vec(),
        mode: mode.to_string(),
        acc_checksum: acc_checksum(acc),
    };
    let path = dir.join(format!("pass_{pass_index}.json"));
    let body = serde_json::to_string_pretty(&record).map_err(|e| e.to_string())?;
    fs::write(path, body).map_err(|e| e.to_string())
}

fn maybe_midwindow_snapshot(
    plan: &TrainingPlan,
    store: &Store,
    wal: &mut WalTail,
    out: &Path,
    phase: StepPhase,
    buf: &AccBuf,
    completed_steps: u32,
    wave_offset: u32,
    seq: i64,
    slot: u32,
    tag: u64,
    fp: &str,
    sink: &mut TraceSink,
) -> Result<bool, String> {
    if let Some(after_admits) = plan.snapshot_after_admits {
        if buf.tags.len() == after_admits as usize && phase == StepPhase::Folding {
            let mark = seal_v(store, phase, buf, completed_steps, wave_offset);
            sink.write_seal(seq, slot, tag, fp, completed_steps)?;
            wal.append(&format!(
                "seal:{}:{}",
                mark.last_step,
                buf.tags
                    .iter()
                    .map(|t| t.to_string())
                    .collect::<Vec<_>>()
                    .join(",")
            ));
            wal.flush(&out.join("wal.log"))?;
            write_manifest(store, &mark)?;
            return Ok(true);
        }
    }
    Ok(false)
}

fn append_wal_seal(wal: &mut WalTail, out: &Path, mark: &crate::q_st::SealMark, tags: &[u64]) -> Result<(), String> {
    wal.append(&format!(
        "seal:{}:{}",
        mark.last_step,
        tags.iter().map(|t| t.to_string()).collect::<Vec<_>>().join(",")
    ));
    wal.flush(&out.join("wal.log"))
}

pub fn run_train(
    plan: &TrainingPlan,
    mode: RunMode,
    seed: u64,
    accum_steps: usize,
    out: &PathBuf,
) -> Result<(), String> {
    let schedule = SchedulePlan::from_plan(plan, mode, seed, accum_steps);
    let mut lane = PendingLane::default();
    let mut buf = AccBuf::new(accum_steps);
    let mut sink = TraceSink::open(out)?;
    let store = Store::new(out.join("vault"));
    let mut wal = WalTail::default();
    let mut seq = 0i64;
    let mut admit_count = 0u64;
    let mut completed_steps = 0u64;
    let mut pass_index = 0u32;

    for wave in schedule.waves() {
        let mut wave_offset = 0u32;
        for slot in wave {
            let payload = plan.payload_for_slot(slot);
            let tag = lane.admit(slot, seq as u64, &payload);
            seq += 1;
            admit_count += 1;
            wave_offset += 1;
            let fp = payload_fp(&payload);
            sink.write_admit(seq, slot, tag, &fp, completed_steps as u32)?;

            let phase = fold_u(&mut buf, tag, &payload);
            sink.write_fold(seq, slot, tag, &fp, completed_steps as u32)?;

            if maybe_midwindow_snapshot(
                plan,
                &store,
                &mut wal,
                out,
                phase,
                &buf,
                completed_steps as u32,
                wave_offset,
                seq,
                slot,
                tag,
                &fp,
                &mut sink,
            )? {
                sink.flush()?;
                return Ok(());
            }

            if phase == StepPhase::StepReady {
                let digest = step_fp(completed_steps as u32, &buf.tags, mode.as_str());
                let tally = acct::tally_admits(admit_count, accum_steps as u64, completed_steps);
                let pending = lane.pending_slots();
                write_pass(
                    out,
                    pass_index,
                    &digest,
                    tally,
                    &pending,
                    mode.as_str(),
                    &buf.acc,
                )?;
                pass_index += 1;
                emit_gauge(&buf, plan.gauge_ceiling);
                sink.write_step(seq, slot, tag, &fp, completed_steps as u32)?;

                if let Some(snapshot_at) = plan.snapshot_step {
                    if snapshot_at == completed_steps as u32 + 1 {
                        let mark = seal_v(
                            &store,
                            phase,
                            &buf,
                            completed_steps as u32,
                            0,
                        );
                        sink.write_seal(seq, slot, tag, &fp, completed_steps as u32)?;
                        append_wal_seal(&mut wal, out, &mark, &buf.tags)?;
                        write_manifest(&store, &mark)?;
                        completed_steps += 1;
                        buf.reset_window();
                        sink.flush()?;
                        return Ok(());
                    }
                }

                if let Some(snapshot_at) = plan.continue_snapshot_step {
                    if snapshot_at == completed_steps as u32 + 1 {
                        let mark = seal_v(
                            &store,
                            phase,
                            &buf,
                            completed_steps as u32,
                            0,
                        );
                        sink.write_seal(seq, slot, tag, &fp, completed_steps as u32)?;
                        append_wal_seal(&mut wal, out, &mark, &buf.tags)?;
                        write_manifest(&store, &mark)?;
                        completed_steps += 1;
                        buf.reset_window();
                        sink.flush()?;
                        return Ok(());
                    }
                }

                completed_steps += 1;
                buf.reset_window();
                wave_offset = 0;
            }
        }
    }
    sink.flush()?;
    Ok(())
}

pub fn run_continue(
    plan: &TrainingPlan,
    mode: RunMode,
    seed: u64,
    accum_steps: usize,
    from: &PathBuf,
    out: &PathBuf,
) -> Result<(), String> {
    let mut sink = TraceSink::open(out)?;
    let store = Store::new(from);
    let mut lane = PendingLane::default();
    let plan_cycle = resume_from_vault(&store, &mut lane);
    let schedule = SchedulePlan::from_plan(plan, mode, seed, accum_steps);

    let (mut buf, mark) = load_vault(&store, accum_steps).unwrap_or_else(|_| {
        (
            AccBuf::new(accum_steps),
            crate::q_st::SealMark {
                last_tag: 0,
                last_step: 0,
                pending_count: 0,
                wave_offset: 0,
            },
        )
    });

    if mark.pending_count > 0 {
        buf.tags = plan_cycle.replay_tags.clone();
    }

    let mut seq = sink.max_seq();
    let mut admit_count = sink.admit_count();
    let resume_step = if mark.pending_count > 0 {
        mark.last_step
    } else {
        mark.last_step + 1
    };
    let mut completed_steps = resume_step as u64;
    let mut pass_index = next_pass_index(out);
    let mut wal = WalTail::default();

    for wave in schedule.waves_from_offset(resume_step, plan_cycle.wave_offset) {
        let mut wave_offset = plan_cycle.wave_offset;
        for slot in wave {
            let payload = plan.payload_for_slot(slot);
            let tag = lane.admit(slot, seq as u64, &payload);
            seq += 1;
            admit_count += 1;
            wave_offset += 1;
            let fp = payload_fp(&payload);
            sink.write_admit(seq, slot, tag, &fp, completed_steps as u32)?;

            let phase = fold_u(&mut buf, tag, &payload);
            sink.write_fold(seq, slot, tag, &fp, completed_steps as u32)?;

            if maybe_midwindow_snapshot(
                plan,
                &Store::new(out.join("vault")),
                &mut wal,
                out,
                phase,
                &buf,
                completed_steps as u32,
                wave_offset,
                seq,
                slot,
                tag,
                &fp,
                &mut sink,
            )? {
                sink.flush()?;
                return Ok(());
            }

            if phase == StepPhase::StepReady {
                let digest = step_fp(completed_steps as u32, &buf.tags, mode.as_str());
                let tally = acct::tally_admits(admit_count, accum_steps as u64, completed_steps);
                let pending = lane.pending_slots();
                write_pass(
                    out,
                    pass_index,
                    &digest,
                    tally,
                    &pending,
                    mode.as_str(),
                    &buf.acc,
                )?;
                pass_index += 1;
                emit_gauge(&buf, plan.gauge_ceiling);
                sink.write_step(seq, slot, tag, &fp, completed_steps as u32)?;

                if let Some(snapshot_at) = plan.snapshot_step {
                    if snapshot_at == completed_steps as u32 + 1 {
                        let vault = Store::new(out.join("vault"));
                        let mark = seal_v(
                            &vault,
                            phase,
                            &buf,
                            completed_steps as u32,
                            0,
                        );
                        sink.write_seal(seq, slot, tag, &fp, completed_steps as u32)?;
                        append_wal_seal(&mut wal, out, &mark, &buf.tags)?;
                        write_manifest(&vault, &mark)?;
                        completed_steps += 1;
                        buf.reset_window();
                        sink.flush()?;
                        return Ok(());
                    }
                }

                if let Some(snapshot_at) = plan.continue_snapshot_step {
                    if snapshot_at == completed_steps as u32 + 1 {
                        let vault = Store::new(out.join("vault"));
                        let mark = seal_v(
                            &vault,
                            phase,
                            &buf,
                            completed_steps as u32,
                            0,
                        );
                        write_manifest(&vault, &mark)?;
                        completed_steps += 1;
                        buf.reset_window();
                        sink.flush()?;
                        return Ok(());
                    }
                }

                completed_steps += 1;
                buf.reset_window();
                wave_offset = 0;
            }
        }
    }
    sink.flush()?;
    Ok(())
}

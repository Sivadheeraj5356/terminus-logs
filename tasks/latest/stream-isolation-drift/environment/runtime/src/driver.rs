use super::cycle::continue_from_vault;
use super::sched::{JobPlan, RunMode, SchedulePlan};
use persist::{mark_r, Store, WalTail};
use spawn::PendingLane;
use tape::segment::record_segment;
use vane::{acct, draw_q, emit_gauge, GenPhase, Pool};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

#[derive(Serialize, Deserialize)]
struct TranscriptRow {
    seq: i64,
    job: i32,
    phase: String,
    slot: i64,
    payload_digest: String,
    pass_index: u32,
}

struct TranscriptSink {
    path: PathBuf,
    rows: Vec<TranscriptRow>,
}

impl TranscriptSink {
    fn open(out: &Path) -> Result<Self, String> {
        fs::create_dir_all(out).map_err(|e| e.to_string())?;
        let path = out.join("run_transcript.jsonl");
        let mut rows = Vec::new();
        if path.exists() {
            let body = fs::read_to_string(&path).map_err(|e| e.to_string())?;
            for line in body.lines() {
                if line.trim().is_empty() {
                    continue;
                }
                let row: TranscriptRow = serde_json::from_str(line).map_err(|e| e.to_string())?;
                rows.push(row);
            }
        }
        Ok(Self { path, rows })
    }

    fn max_seq(&self) -> i64 {
        self.rows.iter().map(|row| row.seq).max().unwrap_or(0)
    }

    fn spawn_count(&self) -> u64 {
        self.rows
            .iter()
            .filter(|row| row.phase == "spawn")
            .count() as u64
    }

    fn push(
        &mut self,
        seq: i64,
        job: u32,
        phase: &str,
        slot: u64,
        payload: &str,
        pass_index: u32,
    ) -> Result<(), String> {
        self.rows.push(TranscriptRow {
            seq,
            job: job as i32,
            phase: phase.to_string(),
            slot: slot as i64,
            payload_digest: payload.to_string(),
            pass_index,
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

fn payload_digest(values: &[f64]) -> String {
    let mut bytes = Vec::with_capacity(values.len() * 8);
    for value in values {
        bytes.extend_from_slice(&value.to_le_bytes());
    }
    format!("{:x}", Sha256::digest(&bytes))
}

fn pass_fp(pass_index: u32, slots: &[u64], _mode: &str) -> String {
    let mut sorted = slots.to_vec();
    sorted.sort_unstable();
    let csv = sorted
        .iter()
        .map(|slot| slot.to_string())
        .collect::<Vec<_>>()
        .join(",");
    let payload = format!("pass:{pass_index};slots:{csv}");
    let hash = Sha256::digest(payload.as_bytes());
    format!("{:x}", hash)[..16].to_string()
}

#[derive(Serialize)]
struct PassRecord {
    stream_fingerprint: String,
    open_slots: Vec<i32>,
    mode: String,
}

fn next_pass_index(out: &Path) -> u32 {
    let dir = out.join("pass_records");
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
    fp: &str,
    open_slots: &[i32],
    mode: &str,
) -> Result<(), String> {
    let dir = out.join("pass_records");
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let record = PassRecord {
        stream_fingerprint: fp.to_string(),
        open_slots: open_slots.to_vec(),
        mode: mode.to_string(),
    };
    let path = dir.join(format!("pass_{pass_index}.json"));
    let body = serde_json::to_string_pretty(&record).map_err(|e| e.to_string())?;
    fs::write(path, body).map_err(|e| e.to_string())
}

pub fn run_train(
    plan: &JobPlan,
    mode: RunMode,
    mix: u64,
    out: &PathBuf,
) -> Result<(), String> {
    let schedule = SchedulePlan::from_plan(plan, mode, mix);
    let mut lane = PendingLane::default();
    let mut pool = Pool::new(plan.window);
    let mut sink = TranscriptSink::open(out)?;
    let store = Store::new(out.join("vault"));
    let mut wal = WalTail::default();
    let mut seq = 0i64;
    let mut spawn_total = 0u64;
    let mut completed_passes = 0u64;
    let mut pass_index = 0u32;
    let plan_tag = plan.version;

    for wave in schedule.waves() {
        for job in wave {
            let draws = plan.draws_for_job(job);
            let slot = lane.admit(job, seq as u64, plan_tag, &draws);
            seq += 1;
            spawn_total += 1;
            let fp = payload_digest(&draws);
            sink.push(seq, job, "spawn", slot, &fp, completed_passes as u32)?;

            let phase = draw_q(&mut pool, slot, &draws);
            sink.push(seq, job, "draw", slot, &fp, completed_passes as u32)?;
            let _seg = record_segment(slot, &draws);
            sink.push(seq, job, "tape", slot, &fp, completed_passes as u32)?;

            if phase == GenPhase::PassReady {
                let slots = acct::slots_for_pass(&pool);
                let fp_chain = pass_fp(completed_passes as u32, &slots, mode.as_str());
                let open = lane.open_jobs();
                write_pass(out, pass_index, &fp_chain, &open, mode.as_str())?;
                pass_index += 1;
                emit_gauge(&pool, plan.gauge_ceiling);
                sink.push(seq, job, "step", slot, &fp, completed_passes as u32)?;

                if let Some(checkpoint_at) = plan.checkpoint_pass {
                    if checkpoint_at == completed_passes as u32 + 1 {
                        let mark = mark_r(&store, phase, &pool);
                        sink.push(seq, job, "seal", slot, &fp, completed_passes as u32)?;
                        wal.append(&format!(
                            "seal:{}:{}",
                            mark.last_pass, mark.last_generation
                        ));
                        wal.flush(&out.join("wal.log"))?;
                        let mut manifest = mark;
                        manifest.last_pass = completed_passes as u32;
                        persist::write_manifest(&store, &manifest)?;
                        completed_passes += 1;
                        pool.reset_pass();
                        sink.flush()?;
                        return Ok(());
                    }
                }

                completed_passes += 1;
                pool.reset_pass();
            }
        }
    }
    sink.flush()?;
    Ok(())
}

pub fn run_continue(
    plan: &JobPlan,
    mode: RunMode,
    mix: u64,
    from: &PathBuf,
    out: &PathBuf,
) -> Result<(), String> {
    let mut sink = TranscriptSink::open(out)?;
    let store = Store::new(from);
    let mut lane = PendingLane::default();
    let plan_cycle = continue_from_vault(&store, &mut lane);
    let schedule = SchedulePlan::from_plan(plan, mode, mix);
    let mut pool = Pool::new(plan.window);
    let mut seq = sink.max_seq();
    let mut spawn_total = sink.spawn_count();
    let mut completed_passes = plan_cycle.halt_pass as u64 + 1;
    let mut pass_index = next_pass_index(out);
    let plan_tag = plan.version;

    for wave in schedule.waves_from(plan_cycle.halt_pass + 1) {
        for job in wave {
            let draws = plan.draws_for_job(job);
            let slot = lane.admit(job, seq as u64, plan_tag, &draws);
            seq += 1;
            spawn_total += 1;
            let fp = payload_digest(&draws);
            sink.push(seq, job, "spawn", slot, &fp, completed_passes as u32)?;

            let phase = draw_q(&mut pool, slot, &draws);
            sink.push(seq, job, "draw", slot, &fp, completed_passes as u32)?;
            let _seg = record_segment(slot, &draws);
            sink.push(seq, job, "tape", slot, &fp, completed_passes as u32)?;

            if phase == GenPhase::PassReady {
                let slots = acct::slots_for_pass(&pool);
                let fp_chain = pass_fp(completed_passes as u32, &slots, mode.as_str());
                let open = lane.open_jobs();
                write_pass(out, pass_index, &fp_chain, &open, mode.as_str())?;
                pass_index += 1;
                emit_gauge(&pool, plan.gauge_ceiling);
                sink.push(seq, job, "step", slot, &fp, completed_passes as u32)?;

                if let Some(checkpoint_at) = plan.continue_checkpoint_pass {
                    if checkpoint_at == completed_passes as u32 + 1 {
                        let mark = mark_r(&store, phase, &pool);
                        let mut manifest = mark;
                        manifest.last_pass = completed_passes as u32;
                        persist::write_manifest(&store, &manifest)?;
                        completed_passes += 1;
                        pool.reset_pass();
                        sink.flush()?;
                        return Ok(());
                    }
                }

                completed_passes += 1;
                pool.reset_pass();
            }
        }
    }
    sink.flush()?;
    Ok(())
}

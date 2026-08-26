use crate::ledger::SeatLedger;
use crate::publication::{
    capture_prior, cleanup_artifacts, cleanup_temp_siblings, publish_staged, restore_prior,
    stage_path,
};
use crate::replay::ReplayContext;
use crate::report::build_report;
use std::fs;
use std::path::{Path, PathBuf};

pub fn run(events_path: &str, log_path: &str, report_path: Option<&str>) -> Result<(), String> {
    let log_target = PathBuf::from(log_path);
    let report_target = report_path.map(PathBuf::from);
    let prior = capture_prior(&log_target, report_target.as_deref())?;

    let parent = log_target
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from("."));
    fs::create_dir_all(&parent).map_err(|e| e.to_string()).or_else(|err| {
        restore_prior(&log_target, report_target.as_deref(), &prior)?;
        Err(err)
    })?;

    let stage_log = stage_path(&log_target);
    let stage_report = report_target.as_ref().map(|path| stage_path(path));
    let mut cleanup = vec![stage_log.clone()];
    if let Some(path) = &stage_report {
        cleanup.push(path.clone());
    }

    if let Some(bytes) = &prior.log {
        fs::write(&stage_log, bytes).map_err(|e| e.to_string())?;
    } else {
        fs::write(&stage_log, "").map_err(|e| e.to_string())?;
    }

    let mut ctx = ReplayContext::new(SeatLedger::new());
    ctx.log_path = Some(stage_log.to_string_lossy().into_owned());
    let max_seq = ReplayContext::max_log_seq(stage_log.to_string_lossy().as_ref())?;
    ctx.seed_emit_seq(if max_seq == 0 { 1 } else { max_seq.saturating_add(1) });

    if let Err(err) = ctx.replay_file(events_path, "/app/data/rams") {
        cleanup_artifacts(&cleanup);
        cleanup_temp_siblings(&log_target);
        if let Some(path) = &report_target {
            cleanup_temp_siblings(path);
        }
        restore_prior(&log_target, report_target.as_deref(), &prior)?;
        return Err(err.to_string());
    }

    if let Some(path) = &stage_report {
        let guides = count_guide_mark(stage_log.to_string_lossy().as_ref())?;
        let body = build_report(&ctx.ledger, false, guides);
        if let Err(err) = fs::write(path, serde_json::to_string_pretty(&body).unwrap() + "\n") {
            cleanup_artifacts(&cleanup);
            cleanup_temp_siblings(&log_target);
            if let Some(report_path) = &report_target {
                cleanup_temp_siblings(report_path);
            }
            restore_prior(&log_target, report_target.as_deref(), &prior)?;
            return Err(err.to_string());
        }
    }

    if let Err(err) = publish_staged(&stage_log, &log_target) {
        cleanup_artifacts(&cleanup);
        cleanup_temp_siblings(&log_target);
        if let Some(path) = &report_target {
            cleanup_temp_siblings(path);
        }
        restore_prior(&log_target, report_target.as_deref(), &prior)?;
        return Err(err);
    }
    cleanup.retain(|path| path != &stage_log);

    if let (Some(stage), Some(target)) = (&stage_report, &report_target) {
        if let Err(err) = publish_staged(stage, target) {
            cleanup_artifacts(&cleanup);
            cleanup_temp_siblings(&log_target);
            cleanup_temp_siblings(target);
            restore_prior(&log_target, report_target.as_deref(), &prior)?;
            return Err(err);
        }
    }

    cleanup_artifacts(&cleanup);
    Ok(())
}

fn count_guide_mark(log_path: &str) -> Result<u32, String> {
    let text = fs::read_to_string(log_path).map_err(|e| e.to_string())?;
    Ok(text
        .lines()
        .filter(|line| line.contains("\"guide_marked\""))
        .count() as u32)
}

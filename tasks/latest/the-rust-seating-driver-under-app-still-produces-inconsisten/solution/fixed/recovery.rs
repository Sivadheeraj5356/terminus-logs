use crate::ledger::SeatLedger;
use crate::replay::{ReplayContext, ReplayError};
use std::fs;
use std::path::Path;

#[derive(Debug)]
pub enum RecoveryError {
    Anchor(String),
    Replay(ReplayError),
}

impl RecoveryError {
    pub fn fatal_message(&self) -> String {
        match self {
            RecoveryError::Anchor(msg) => msg.clone(),
            RecoveryError::Replay(err) => err.to_string(),
        }
    }
}

pub fn replay_with_recovery(
    events_path: &str,
    data_root: &str,
    snapshot_path: &str,
    log_path: &str,
) -> Result<(SeatLedger, bool), RecoveryError> {
    let baseline =
        SeatLedger::load_from_file(snapshot_path).map_err(RecoveryError::Anchor)?;
    let backup_rams = baseline.snapshot();
    let backup_epoch = baseline.cycle_epoch();
    let backup_rev = baseline.journal_revision();

    if !Path::new(log_path).exists() {
        fs::write(log_path, "").map_err(|e| RecoveryError::Anchor(e.to_string()))?;
    }

    let mut ctx = ReplayContext::new(baseline);
    ctx.log_path = Some(log_path.to_string());
    let max_seq = ReplayContext::max_log_seq(log_path).map_err(|e| RecoveryError::Anchor(e))?;
    ctx.seed_emit_seq(if max_seq == 0 { 1 } else { max_seq.saturating_add(1) });

    match ctx.replay_file(events_path, data_root) {
        Ok(()) => Ok((ctx.ledger, false)),
        Err(ReplayError::CmprBlock(_)) => {
            ctx.ledger
                .restore_baseline(backup_rams, backup_epoch, backup_rev);
            Ok((ctx.ledger, true))
        }
        Err(other) => Err(RecoveryError::Replay(other)),
    }
}

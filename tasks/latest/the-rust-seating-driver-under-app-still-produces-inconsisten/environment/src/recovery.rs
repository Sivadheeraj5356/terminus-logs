use crate::ledger::SeatLedger;
use crate::replay::ReplayContext;

pub fn replay_with_recovery(
    events_path: &str,
    data_root: &str,
    snapshot_path: &str,
    log_path: &str,
) -> Result<(SeatLedger, bool), String> {
    let baseline = SeatLedger::load_from_file(snapshot_path)?;
    let backup_rams = baseline.snapshot();
    let backup_epoch = baseline.cycle_epoch();
    let backup_rev = baseline.journal_revision();
    let mut ctx = ReplayContext::new(baseline);
    ctx.log_path = Some(log_path.to_string());
    match ctx.replay_file(events_path, data_root) {
        Ok(()) => Ok((ctx.ledger, false)),
        Err(_) => {
            ctx.ledger
                .restore_baseline(backup_rams, backup_epoch, backup_rev);
            Ok((ctx.ledger, true))
        }
    }
}

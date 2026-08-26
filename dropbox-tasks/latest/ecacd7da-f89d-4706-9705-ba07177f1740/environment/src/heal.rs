use crate::replay::ReplayContext;
use crate::store::Store;

pub fn seat_with_recovery(
    journal_path: &str,
    data_root: &str,
    snapshot_path: &str,
    log_path: &str,
) -> Result<(Store, bool), String> {
    let baseline = Store::load_from_file(snapshot_path)?;
    let backup_records = baseline.records_snapshot();
    let backup_epoch = baseline.quota_epoch();
    let backup_revision = baseline.journal_revision();
    let mut ctx = ReplayContext::new(baseline);
    ctx.log_path = Some(log_path.to_string());
    match ctx.replay_file(journal_path, data_root) {
        Ok(()) => Ok((ctx.store, false)),
        Err(_) => {
            ctx.store
                .restore_full_state(backup_records, backup_epoch, backup_revision);
            Ok((ctx.store, true))
        }
    }
}

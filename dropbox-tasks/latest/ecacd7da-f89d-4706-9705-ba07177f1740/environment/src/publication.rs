pub fn publish_normal_run(
    events_path: &str,
    log_path: &str,
    report_path: Option<&str>,
) -> Result<(), String> {
    crate::normal_run::run(events_path, log_path, report_path)
}

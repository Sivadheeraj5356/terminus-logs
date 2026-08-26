pub fn run(events_path: &str, log_path: &str, report_path: Option<&str>) -> Result<(), String> {
    crate::staged_run::run(events_path, log_path, report_path)
}

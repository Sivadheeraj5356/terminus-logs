use crate::publication;

pub fn run(events_path: &str, log_path: &str, report_path: Option<&str>) -> Result<(), String> {
    publication::publish_normal_run(events_path, log_path, report_path)
}

use hx01::status::StatusReport;
use hx01::Result;

pub fn print_status(report: &StatusReport, json: bool) -> Result<()> {
    if json {
        println!("{}", serde_json::to_string_pretty(report)?);
    } else {
        println!(
            "phase={} generation={} managed={} foreign={}",
            report.phase, report.generation, report.managed_rules, report.foreign_rules
        );
    }
    Ok(())
}

pub fn flag_value(args: &[String], name: &str) -> Result<String, String> {
    args.iter()
        .position(|a| a == name)
        .and_then(|i| args.get(i + 1))
        .cloned()
        .ok_or_else(|| format!("missing value for {name}"))
}

pub fn optional_flag_value(args: &[String], name: &str) -> Option<String> {
    args.iter()
        .position(|a| a == name)
        .and_then(|i| args.get(i + 1))
        .cloned()
}

pub fn run_seat(args: &[String]) -> Result<(), String> {
    let events = flag_value(args, "--seat")?;
    let log = flag_value(args, "--emit-log")?;
    let report = optional_flag_value(args, "--emit-report");
    crate::staged_run::run(&events, &log, report.as_deref())
}

pub fn run_recover_seat(args: &[String]) -> Result<(), String> {
    let events = flag_value(args, "--seat-recover")?;
    let log = flag_value(args, "--emit-log")?;
    let report = optional_flag_value(args, "--emit-report");
    crate::recover_run::run(&events, &log, report.as_deref())
}

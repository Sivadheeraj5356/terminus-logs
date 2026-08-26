pub enum Mode {
    Analyze,
    CheckCoin(String),
    Export,
    Version,
}

pub fn parse_mode(args: &[String]) -> Mode {
    if args.is_empty() {
        return Mode::Analyze;
    }
    match args[0].as_str() {
        "analyze" => Mode::Analyze,
        "export" => Mode::Export,
        "version" => Mode::Version,
        "check-coin" => {
            if args.len() < 2 {
                Mode::Analyze
            } else {
                Mode::CheckCoin(args[1].clone())
            }
        }
        _ => Mode::Analyze,
    }
}

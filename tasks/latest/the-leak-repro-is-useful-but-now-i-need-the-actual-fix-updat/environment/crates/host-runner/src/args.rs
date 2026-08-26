use std::env;
use std::path::PathBuf;

#[derive(Clone, Debug)]
pub struct Args {
    pub component: PathBuf,
    pub fixtures: PathBuf,
    pub mode: String,
    pub report: PathBuf,
}

impl Args {
    pub fn parse() -> Result<Self, String> {
        let mut component = None;
        let mut fixtures = None;
        let mut mode = None;
        let mut report = None;
        let mut iter = env::args().skip(1);
        while let Some(flag) = iter.next() {
            let value = iter
                .next()
                .ok_or_else(|| format!("missing value for {flag}"))?;
            match flag.as_str() {
                "--component" => component = Some(PathBuf::from(value)),
                "--fixtures" => fixtures = Some(PathBuf::from(value)),
                "--mode" => mode = Some(value),
                "--report" => report = Some(PathBuf::from(value)),
                other => return Err(format!("unknown flag {other}")),
            }
        }
        Ok(Self {
            component: component.ok_or("missing --component")?,
            fixtures: fixtures.ok_or("missing --fixtures")?,
            mode: mode.ok_or("missing --mode")?,
            report: report.ok_or("missing --report")?,
        })
    }
}

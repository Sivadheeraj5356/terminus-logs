use std::collections::HashSet;

#[derive(Debug)]
pub struct Args {
    pub data_dir: String,
    pub output: String,
}

impl Args {
    pub fn parse(args: impl IntoIterator<Item = String>) -> Result<Self, String> {
        let mut data_dir: Option<String> = None;
        let mut output: Option<String> = None;
        let mut seen = HashSet::new();
        let mut it = args.into_iter();
        while let Some(a) = it.next() {
            if !seen.insert(a.clone()) {
                return Err(format!("duplicate argument: {a}"));
            }
            match a.as_str() {
                "--data-dir" => {
                    let v = it
                        .next()
                        .ok_or_else(|| "missing --data-dir value".to_string())?;
                    if data_dir.replace(v).is_some() {
                        return Err("duplicate argument: --data-dir".into());
                    }
                }
                "--output" => {
                    let v = it
                        .next()
                        .ok_or_else(|| "missing --output value".to_string())?;
                    if output.replace(v).is_some() {
                        return Err("duplicate argument: --output".into());
                    }
                }
                other => return Err(format!("unknown argument: {other}")),
            }
        }
        Ok(Self {
            data_dir: data_dir.ok_or_else(|| "missing --data-dir".to_string())?,
            output: output.ok_or_else(|| "missing --output".to_string())?,
        })
    }
}

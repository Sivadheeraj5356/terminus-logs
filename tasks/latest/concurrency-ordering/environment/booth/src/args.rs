pub struct Opts {
    pub cmd: String,
    pub scenario: Option<String>,
    pub journal: Option<String>,
    pub out_dir: String,
    pub tag: Option<String>,
    pub seed: Option<u64>,
}

pub fn parse(args: &[String]) -> Result<Opts, String> {
    if args.len() < 2 {
        return Err("usage: arena_cli <run|resume> ...".into());
    }
    let cmd = args[1].clone();
    let mut scenario = None;
    let mut journal = None;
    let mut out_dir = "/app/output/runs".to_string();
    let mut tag = None;
    let mut seed = None;
    let mut i = 2usize;
    while i < args.len() {
        match args[i].as_str() {
            "--scenario" => {
                i += 1;
                scenario = Some(args.get(i).ok_or("--scenario needs value")?.clone());
            }
            "--journal" => {
                i += 1;
                journal = Some(args.get(i).ok_or("--journal needs value")?.clone());
            }
            "--out" => {
                i += 1;
                out_dir = args.get(i).ok_or("--out needs value")?.clone();
            }
            "--tag" => {
                i += 1;
                tag = Some(args.get(i).ok_or("--tag needs value")?.clone());
            }
            "--seed" => {
                i += 1;
                seed = Some(
                    args.get(i)
                        .ok_or("--seed needs value")?
                        .parse::<u64>()
                        .map_err(|_| "bad seed")?,
                );
            }
            other => return Err(format!("unknown arg {}", other)),
        }
        i += 1;
    }
    Ok(Opts {
        cmd,
        scenario,
        journal,
        out_dir,
        tag,
        seed,
    })
}

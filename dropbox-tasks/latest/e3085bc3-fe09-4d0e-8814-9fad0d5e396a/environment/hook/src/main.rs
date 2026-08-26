mod lane;
mod load;
mod path;

use std::io::Write;

fn arg(flag: &str) -> Option<String> {
    let mut it = std::env::args();
    while let Some(a) = it.next() {
        if a == flag {
            return it.next();
        }
    }
    None
}

fn fnv1a(seed: u64, bytes: &[u8]) -> u64 {
    let mut h = seed;
    for &b in bytes {
        h ^= b as u64;
        h = h.wrapping_mul(0x100000001b3);
    }
    h
}

fn main() {
    let program_path = arg("--program").unwrap_or_else(|| "output/program.json".to_string());
    let jobs_path = arg("--jobs").unwrap_or_else(|| "output/jobs.txt".to_string());
    let manifest_path = arg("--manifest").unwrap_or_else(|| "data/manifest.json".to_string());
    let traces_path = arg("--traces").unwrap_or_else(|| "output/read_traces.json".to_string());
    let log_path = arg("--log").unwrap_or_else(|| "output/measure_log.json".to_string());

    let prog = load::load_program(&program_path);
    let jobs = load::load_jobs(&jobs_path);
    let manifest = load::load_manifest(&manifest_path);

    let mut digest: u64 = 0xcbf29ce484222325;
    let mut jobs_json: Vec<String> = Vec::new();
    let mut rows: Vec<String> = Vec::new();

    for job in &jobs {
        let mut events: Vec<String> = Vec::new();
        for path in &job.reads {
            let canon = path::canonical(path);
            let tier = load::lane_of(&prog.clauses, &canon);
            let verbs = load::bits_at(&prog.clauses, tier, &canon);
            digest = fnv1a(digest, path.as_bytes());
            let verb_json: Vec<String> = verbs.iter().map(|v| v.to_string()).collect();
            events.push(format!(
                "{{\"path\":\"{}\",\"verbs\":[{}]}}",
                path,
                verb_json.join(",")
            ));
            if lane::wants_log(&verbs) {
                let key = lane::mark_id(path);
                let d = load::digest_for(&manifest, &canon);
                rows.push(format!(
                    "{{\"path\":\"{}\",\"digest_hex\":\"{}\"}}",
                    key, d
                ));
            }
        }
        jobs_json.push(format!(
            "{{\"name\":\"{}\",\"events\":[{}]}}",
            job.name,
            events.join(",")
        ));
    }

    let traces_body = format!(
        "{{\n  \"set_id\": \"{:016x}\",\n  \"jobs\": [{}]\n}}\n",
        digest,
        jobs_json.join(",")
    );
    let log_body = format!(
        "{{\n  \"set_id\": \"{:016x}\",\n  \"rows\": [{}]\n}}\n",
        digest,
        rows.join(",")
    );

    let mut tf = std::fs::File::create(&traces_path).expect("create traces");
    tf.write_all(traces_body.as_bytes()).expect("write traces");
    let mut lf = std::fs::File::create(&log_path).expect("create log");
    lf.write_all(log_body.as_bytes()).expect("write log");
}

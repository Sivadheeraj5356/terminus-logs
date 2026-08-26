use std::fs;
use std::path::Path;

pub fn record(ingest_seq: u64, assay_bind: &str) -> Result<(), String> {
    let path = Path::new("/app/state/assay-ledger.jsonl");
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let line = format!("{{\"ingest_seq\":{ingest_seq},\"assay_bind\":\"{assay_bind}\"}}\n");
    use std::io::Write;
    let mut f = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|e| e.to_string())?;
    f.write_all(line.as_bytes()).map_err(|e| e.to_string())?;
    Ok(())
}

pub fn verify_matches_snapshot(ingest_seq: u64, assay_bind: &str) -> Result<(), String> {
    let path = Path::new("/app/state/assay-ledger.jsonl");
    if !path.is_file() {
        return Err("missing ledger".to_string());
    }
    let text = fs::read_to_string(path).map_err(|e| e.to_string())?;
    let mut ok = false;
    for line in text.lines() {
        if line.contains(&format!("\"ingest_seq\":{ingest_seq}"))
            && line.contains(&format!("\"assay_bind\":\"{assay_bind}\""))
        {
            ok = true;
        }
    }
    if !ok {
        return Err("ledger does not match snapshot".to_string());
    }
    Ok(())
}

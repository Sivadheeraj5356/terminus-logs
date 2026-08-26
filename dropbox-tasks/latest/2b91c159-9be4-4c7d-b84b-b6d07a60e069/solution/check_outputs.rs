mod grade_model;

use grade_model::expected_report;
use std::fs;
use std::process::Command;

fn finite_close(got: f64, want: f64) -> bool {
    if got.is_nan() || want.is_nan() {
        return false;
    }
    let tiny = 1e-13_f64;
    let rel = tiny * (got.abs() + want.abs() + 1.0);
    let tol = if tiny > rel { tiny } else { rel };
    (got - want).abs() <= tol
}

fn get_json_string(blob: &str, key: &str) -> Option<String> {
    let marker = format!("\"{key}\"");
    let pos = blob.find(&marker)?;
    let rest = &blob[pos + marker.len()..];
    let colon = rest.find(':')?;
    let value = rest[colon + 1..].trim_start();
    if !value.starts_with('"') {
        return None;
    }
    let tail = &value[1..];
    let end = tail.find('"')?;
    Some(tail[..end].to_string())
}

fn get_json_number(blob: &str, key: &str) -> Option<f64> {
    let marker = format!("\"{key}\"");
    let pos = blob.find(&marker)?;
    let rest = &blob[pos + marker.len()..];
    let colon = rest.find(':')?;
    let value = rest[colon + 1..].trim_start();
    let end = value
        .find(|c: char| !(c.is_ascii_digit() || c == '.' || c == '-' || c == '+' || c == 'e' || c == 'E'))
        .unwrap_or(value.len());
    value[..end].parse::<f64>().ok()
}

fn run_emit(label: &str, out: &str) -> Result<(), String> {
    let status = Command::new("/app/build/demo_engine")
        .args(["emit", label, out])
        .status()
        .map_err(|e| format!("failed to launch demo_engine: {e}"))?;
    if !status.success() {
        return Err(format!("demo_engine failed for {label} with status {status}"));
    }
    Ok(())
}

fn main() -> Result<(), String> {
    for mode in 0..9 {
        let label = format!("Q{mode}");
        let exp = expected_report(mode);
        let path = format!("/tmp/oracle_ck_{label}.json");
        run_emit(&label, &path)?;

        let blob = fs::read_to_string(&path).map_err(|e| format!("failed to read {path}: {e}"))?;
        let scene = get_json_string(&blob, "scene_token").ok_or("missing scene_token")?;
        if scene != label {
            return Err(format!("scene mismatch for {label}: got {scene}"));
        }

        let got_ledger = get_json_number(&blob, "ledger_tail").ok_or("missing ledger_tail")? as u64;
        if got_ledger != exp.ledger_tail {
            return Err(format!(
                "ledger mismatch for {label}: got {got_ledger}, want {}",
                exp.ledger_tail
            ));
        }

        let got_near = get_json_number(&blob, "scalar_near").ok_or("missing scalar_near")?;
        if !finite_close(got_near, exp.scalar_near) {
            return Err(format!(
                "near mismatch for {label}: got {got_near}, want {}",
                exp.scalar_near
            ));
        }

        let got_addon = get_json_number(&blob, "addon_aux").ok_or("missing addon_aux")?;
        if !finite_close(got_addon, exp.addon_aux) {
            return Err(format!(
                "addon mismatch for {label}: got {got_addon}, want {}",
                exp.addon_aux
            ));
        }

        let got_wrap = get_json_number(&blob, "wrap_epoch").ok_or("missing wrap_epoch")? as u32;
        if got_wrap != exp.wrap_epoch {
            return Err(format!(
                "wrap_epoch mismatch for {label}: got {got_wrap}, want {}",
                exp.wrap_epoch
            ));
        }

        let got_stamp = get_json_number(&blob, "refresh_stamp").ok_or("missing refresh_stamp")? as u64;
        if got_stamp != exp.refresh_stamp {
            return Err(format!(
                "refresh_stamp mismatch for {label}: got {got_stamp}, want {}",
                exp.refresh_stamp
            ));
        }

        let got_gen = get_json_number(&blob, "segment_generation")
            .ok_or("missing segment_generation")? as u32;
        if got_gen != exp.segment_generation {
            return Err(format!(
                "segment_generation mismatch for {label}: got {got_gen}, want {}",
                exp.segment_generation
            ));
        }

        let got_crc = get_json_number(&blob, "journal_crc32").ok_or("missing journal_crc32")? as u32;
        if got_crc != exp.journal_crc32 {
            return Err(format!(
                "journal_crc32 mismatch for {label}: got {got_crc}, want {}",
                exp.journal_crc32
            ));
        }
    }

    let q0 = fs::read_to_string("/tmp/oracle_ck_Q0.json")
        .map_err(|e| format!("failed to read /tmp/oracle_ck_Q0.json: {e}"))?;
    fs::write("/app/output/recovery_report.json", q0)
        .map_err(|e| format!("failed to write /app/output/recovery_report.json: {e}"))?;

    Ok(())
}

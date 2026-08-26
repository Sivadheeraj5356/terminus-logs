use crate::haar;
use crate::ingest::TraceSnapshot;
use crate::seal;
use crate::staging::{
    self, CoeffPack, DenoisedTraces, NoiseAudit, ThresholdJournal, TraceAudit,
};
use crate::Paths;
use sha2::{Digest, Sha256};
use std::fs;

pub fn reconstruct_export(paths: &Paths) -> Result<(), String> {
    crate::ensure_dir(&paths.output)?;
    let snap: TraceSnapshot = staging::read_json(&paths.state.join("trace-snapshot.json"))?;
    let pack: CoeffPack = staging::read_json(&paths.state.join("coeff-pack.json"))?;
    let journal: ThresholdJournal = staging::read_json(&paths.state.join("threshold-journal.json"))?;

    seal::verify_pack(&pack, &snap)?;

    let mut denoised = Vec::new();
    let mut audits = Vec::new();
    let mut total_signal = 0.0;
    let mut total_resid = 0.0;

    let mut snap_by_id = std::collections::BTreeMap::new();
    for t in &snap.traces {
        snap_by_id.insert(t.trace_id.clone(), t);
    }

    for entry in &pack.entries {
        let orig = snap_by_id
            .get(&entry.trace_id)
            .ok_or_else(|| format!("missing snapshot trace {}", entry.trace_id))?;
        let y = haar::inverse_pyramid(&entry.approx, &entry.details, &entry.pad_lengths);
        let y = staging::round_vec12(&y);
        let signal_energy: f64 = orig.samples.iter().map(|x| x * x).sum();
        let residual_energy: f64 = orig
            .samples
            .iter()
            .zip(y.iter())
            .map(|(x, yy)| {
                let d = x - yy;
                d * d
            })
            .sum();
        let relative = residual_energy / signal_energy.max(1e-18);
        total_signal += signal_energy;
        total_resid += residual_energy;
        denoised.push(serde_json::json!({
            "trace_id": entry.trace_id,
            "samples": y,
        }));
        audits.push(TraceAudit {
            trace_id: entry.trace_id.clone(),
            signal_energy: staging::round12(signal_energy),
            residual_energy: staging::round12(residual_energy),
            relative_residual: staging::round12(relative),
        });
    }

    denoised.sort_by(|a, b| {
        a["trace_id"]
            .as_str()
            .unwrap_or("")
            .cmp(b["trace_id"].as_str().unwrap_or(""))
    });
    audits.sort_by(|a, b| a.trace_id.cmp(&b.trace_id));

    let traces_payload = serde_json::Value::Array(denoised.clone());
    let traces_canon = serde_json::to_vec(&traces_payload).map_err(|e| e.to_string())?;
    let mut hasher = Sha256::new();
    hasher.update(&traces_canon);
    let traces_hash = hex_encode(hasher.finalize().as_slice());

    let mean_rel = if audits.is_empty() {
        0.0
    } else {
        audits.iter().map(|a| a.relative_residual).sum::<f64>() / audits.len() as f64
    };

    let out_traces = DenoisedTraces {
        schema_version: 1,
        policy_revision_id: pack.policy_revision_id,
        effective_levels: pack.effective_levels,
        traces: denoised,
        content_sha256: traces_hash,
    };
    let out_path = paths.output.join("denoised-traces.json");
    staging::write_pretty(&out_path, &out_traces)?;

    let file_bytes = fs::read(&out_path).map_err(|e| e.to_string())?;
    let mut hasher2 = Sha256::new();
    hasher2.update(&file_bytes);
    let file_hash = hex_encode(hasher2.finalize().as_slice());

    let audit = NoiseAudit {
        schema_version: 1,
        policy_revision_id: journal.policy_revision_id,
        mad_sigma: journal.mad_sigma,
        total_signal_energy: staging::round12(total_signal),
        total_residual_energy: staging::round12(total_resid),
        mean_relative_residual: staging::round12(mean_rel),
        trace_audits: audits,
        content_sha256: file_hash,
    };
    staging::write_pretty(&paths.output.join("noise-audit.json"), &audit)?;
    Ok(())
}

fn hex_encode(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

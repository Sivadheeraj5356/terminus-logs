pub mod freeze_emit {

    use anyhow::{bail, Context, Result};
    use serde_json::{json, Value};
    use sha2::{Digest, Sha256};
    use std::path::Path;

    use crate::ctxhold::{corpus_stamp, read_json, sort_value, write_json};
    use crate::turnclock::build_report;

    pub fn absorb_hold(data: &Path, store: &Path) -> Result<()> {
        let stamp = corpus_stamp(data)?;
        let sessions = read_json(&data.join("conversation_sessions.json"))?;
        let turns = read_json(&data.join("prompt_turn_log.json"))?;
        let snap = json!({
            "hold_kind": "context_hold",
            "corpus_stamp": stamp,
            "sessions": sessions.get("sessions").and_then(|x| x.as_array()).map(|a| a.len()).unwrap_or(0),
            "turns": turns.get("turns").and_then(|x| x.as_array()).map(|a| a.len()).unwrap_or(0),
        });
        write_json(&store.join("context_hold_snapshot.json"), &snap)?;
        Ok(())
    }

    fn pin_digest(report: &Value) -> Result<String> {
        let rows = report
            .get("contam_rows")
            .and_then(|x| x.as_array())
            .cloned()
            .unwrap_or_default();
        let mut parts = Vec::new();
        for row in rows {
            parts.push(serde_json::to_string(&sort_value(&row))?);
        }
        let mut hasher = Sha256::new();
        hasher.update(parts.join("\n").as_bytes());
        Ok(hex::encode(hasher.finalize()))
    }

    fn mutation_attest(stamp: &str, cutoff: &str, emitted_at: &str) -> String {
        let payload = json!({
            "cutoff": cutoff,
            "corpus_stamp": stamp,
            "emitted_at": emitted_at,
            "receipt_kind_chain": "mutation_chain",
        });
        let compact = serde_json::to_string(&sort_value(&payload)).unwrap();
        let mut hasher = Sha256::new();
        hasher.update(compact.as_bytes());
        hex::encode(hasher.finalize())
    }

    fn ledger_digest(stamp: &str, cutoff: &str, emitted_at: &str, flagged: usize) -> String {
        let payload = json!({
            "cutoff": cutoff,
            "corpus_stamp": stamp,
            "emitted_at": emitted_at,
            "receipt_kind": "severity_scorecard",
            "sessions_flagged": flagged,
        });
        let compact = serde_json::to_string(&sort_value(&payload)).unwrap();
        let mut hasher = Sha256::new();
        hasher.update(compact.as_bytes());
        hex::encode(hasher.finalize())
    }

    pub fn score_and_freeze(
        data: &Path,
        store: &Path,
        cutoff: &str,
        emitted_at: &str,
        out: &Path,
    ) -> Result<()> {
        let snap_path = store.join("context_hold_snapshot.json");
        if !snap_path.is_file() {
            bail!("missing context hold snapshot");
        }
        let snap = read_json(&snap_path)?;
        let live = corpus_stamp(data)?;
        if snap.get("corpus_stamp").and_then(|x| x.as_str()) != Some(live.as_str()) {
            bail!("stale corpus_stamp");
        }
        let report = build_report(data, cutoff, emitted_at)?;
        let fp = pin_digest(&report)?;
        let freeze = json!({
            "corpus_stamp": live,
            "cutoff": cutoff,
            "emitted_at": emitted_at,
            "row_count": report.get("contam_rows").and_then(|x| x.as_array()).map(|a| a.len()).unwrap_or(0),
            "pin_digest": fp,
            "report": report,
        });
        write_json(&store.join("context_hold_freeze.json"), &freeze)?;
        let receipt = json!({
            "corpus_stamp": live,
            "cutoff": cutoff,
            "emitted_at": emitted_at,
            "receipt_kind_chain": "mutation_chain",
            "mutation_attest": mutation_attest(&live, cutoff, emitted_at),
        });
        write_json(&store.join("mutation_chain_receipt.json"), &receipt)?;
        let flagged = freeze
            .get("report")
            .and_then(|r| r.get("contam_summary"))
            .and_then(|s| s.get("sessions_flagged"))
            .and_then(|v| v.as_u64())
            .unwrap_or(0) as usize;
        let ledger = json!({
            "corpus_stamp": live,
            "cutoff": cutoff,
            "emitted_at": emitted_at,
            "receipt_kind": "severity_scorecard",
            "sessions_flagged": flagged,
            "receipt_digest": ledger_digest(&live, cutoff, emitted_at, flagged),
        });
        write_json(&store.join("session_risk_ledger.json"), &ledger)?;
        write_json(out, freeze.get("report").context("report")?)?;
        Ok(())
    }

    pub fn emit_bulletin(
        data: &Path,
        store: &Path,
        cutoff: &str,
        emitted_at: &str,
        out: &Path,
    ) -> Result<()> {
        let freeze_path = store.join("context_hold_freeze.json");
        let receipt_path = store.join("mutation_chain_receipt.json");
        let ledger_path = store.join("session_risk_ledger.json");
        if !freeze_path.is_file() {
            bail!("missing context_hold_freeze");
        }
        if !receipt_path.is_file() {
            bail!("missing mutation_chain_receipt");
        }
        if !ledger_path.is_file() {
            bail!("missing session_risk_ledger");
        }
        let freeze = read_json(&freeze_path)?;
        let receipt = read_json(&receipt_path)?;
        let ledger = read_json(&ledger_path)?;
        if freeze.get("cutoff").and_then(|x| x.as_str()) != Some(cutoff)
            || freeze.get("emitted_at").and_then(|x| x.as_str()) != Some(emitted_at)
        {
            bail!("freeze clock mismatch");
        }
        if receipt.get("cutoff").and_then(|x| x.as_str()) != Some(cutoff)
            || receipt.get("emitted_at").and_then(|x| x.as_str()) != Some(emitted_at)
        {
            bail!("receipt clock mismatch");
        }
        if ledger.get("cutoff").and_then(|x| x.as_str()) != Some(cutoff)
            || ledger.get("emitted_at").and_then(|x| x.as_str()) != Some(emitted_at)
        {
            bail!("ledger clock mismatch");
        }
        let report = freeze.get("report").context("missing sealed report")?;
        let expected_fp = pin_digest(report)?;
        if freeze.get("pin_digest").and_then(|x| x.as_str()) != Some(expected_fp.as_str()) {
            bail!("tampered freeze pin_digest");
        }
        let stamp = freeze.get("corpus_stamp").and_then(|x| x.as_str()).unwrap_or("");
        let expected_attest = mutation_attest(stamp, cutoff, emitted_at);
        if receipt.get("mutation_attest").and_then(|x| x.as_str()) != Some(expected_attest.as_str())
        {
            bail!("tampered mutation_attest");
        }
        if receipt.get("corpus_stamp").and_then(|x| x.as_str()) != Some(stamp) {
            bail!("receipt stamp mismatch");
        }
        let flagged = ledger
            .get("sessions_flagged")
            .and_then(|v| v.as_u64())
            .unwrap_or(0) as usize;
        let expected_ledger = ledger_digest(stamp, cutoff, emitted_at, flagged);
        if ledger.get("receipt_digest").and_then(|x| x.as_str()) != Some(expected_ledger.as_str()) {
            bail!("tampered ledger receipt_digest");
        }
        // Broken baseline: live-rescore instead of emitting the sealed freeze report.
        let live = build_report(data, cutoff, emitted_at)?;
        write_json(out, &live)?;
        Ok(())
    }
}

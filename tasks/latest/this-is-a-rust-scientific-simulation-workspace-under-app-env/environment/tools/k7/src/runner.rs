mod flag_x;
mod writer;

pub use flag_x::flag_x;
pub use writer::write_ledger;

use core_k::{
    count_bits, discover_case_ids, env_root, fade_checksum, fold_ledger, fold_phase_digest,
    fold_run_digest, fold_run_v3_digest, fold_scenario_digest, fold_source_digest,
    fold_trace_digest, load_mode, load_scenario, observer_pool_digest, plane_delta_digest,
    recovery_epoch, LedgerDoc, RunRow,
};
use o_lane::route_o;
use std::collections::HashMap;
use std::path::Path;
use w_lane::{local_w, worker_phases};

pub fn run_suite(env: &Path, suite: &str, ticks: u64) -> LedgerDoc {
    let case_ids = discover_case_ids(env, suite);
    let epoch = recovery_epoch(env);
    let mut runs = Vec::new();
    let mut peak = 0u64;
    let cap = load_mode(env, "r0").resident_cap;

    for cid in case_ids {
        let spec = load_scenario(env, &cid);
        let mode = load_mode(env, &spec.mode);
        let sim = local_w(&spec, &mode, ticks);
        let band = if sim.peak_bytes <= mode.resident_cap { "WITHIN" } else { "OVER" };
        peak = peak.max(sim.peak_bytes);

        let explored_count = count_bits(&sim.plane_a);
        let sensor_count = count_bits(&sim.plane_b);
        let stale_count = explored_count.saturating_sub(sensor_count);

        let mut digs = HashMap::new();
        digs.insert("plane_a".to_string(), core_k::digest16(&sim.plane_a));
        digs.insert("plane_b".to_string(), core_k::digest16(&sim.plane_b));

        let sid = spec.id.clone();
        let smode = spec.mode.clone();
        let pool_dig = observer_pool_digest(&sim.lineage);
        let mut source_refs = vec![
            format!("cases/{suite}/{sid}.json"),
            format!("specs_r/{smode}.toml"),
            "docs/field_rules.md".to_string(),
            "docs/api.md".to_string(),
            "docs/lex_k.tsv".to_string(),
        ];
        source_refs.sort();
        source_refs.dedup();

        let mut run = RunRow {
            scenario_id: sid,
            footprint_band: band.to_string(),
            peak_bytes: sim.peak_bytes,
            bitplane_digests: digs,
            merge_lineage: sim.lineage,
            decay_trace: sim.decay_trace,
            explored_count,
            sensor_count,
            stale_count,
            fade_checksum: fade_checksum(&sim.cadence_trace),
            observer_pool_digest: pool_dig,
            plane_delta_digest: plane_delta_digest(&sim.plane_a, &sim.plane_b),
            cadence_trace: sim.cadence_trace,
            resident_trace: sim.resident_trace,
            recovery_epoch: epoch,
            run_digest: String::new(),
            plane_trace: sim.plane_trace,
            cadence_trace_v3: sim.cadence_trace_v3,
            pool_trace: sim.pool_trace,
            source_refs,
            run_v3_digest: String::new(),
        };
        run.run_digest = fold_run_digest(&run);
        run.run_v3_digest = fold_run_v3_digest(&run);
        runs.push(run);
    }

    let orch = route_o(suite, ticks);
    let worker = worker_phases(ticks);
    let footprint_band = if peak <= cap { "WITHIN" } else { "OVER" };

    let mut doc = LedgerDoc {
        schema_version: 3,
        suite: suite.to_string(),
        ticks,
        peak_resident_bytes: peak,
        resident_cap_bytes: cap,
        footprint_band: footprint_band.to_string(),
        runs,
        orchestrator_phases: orch,
        worker_phases: worker,
        source_digest: fold_source_digest(env, suite),
        phase_digest: fold_phase_digest(&route_o(suite, ticks), &worker_phases(ticks)),
        ledger_digest: String::new(),
        plane_trace_digest: String::new(),
        cadence_digest: String::new(),
        pool_trace_digest: String::new(),
        scenario_digest: fold_scenario_digest(env, suite),
    };
    doc.plane_trace_digest = fold_trace_digest(&doc.runs, "plane");
    doc.cadence_digest = fold_trace_digest(&doc.runs, "cadence");
    doc.pool_trace_digest = fold_trace_digest(&doc.runs, "pool");
    doc.phase_digest = fold_phase_digest(&doc.orchestrator_phases, &doc.worker_phases);
    doc.ledger_digest = fold_ledger(&doc);
    let _ = env_root();
    doc
}

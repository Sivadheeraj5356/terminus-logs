use crate::haar;
use crate::ingest::TraceSnapshot;
use crate::seal;
use crate::staging::{self, CoeffEntry, CoeffLedger, ThresholdJournal};
use crate::threshold;
use crate::Paths;

pub fn decompose_threshold(paths: &Paths) -> Result<(), String> {
    crate::ensure_dir(&paths.state)?;
    let snap: TraceSnapshot = staging::read_json(&paths.state.join("trace-snapshot.json"))?;
    let mut entries = Vec::new();
    let mut finest_pool: Vec<f64> = Vec::new();
    let mut detail_coeff_count = 0usize;
    let mut thresholded_zero_count = 0usize;

    let mut global_levels = 0u32;
    let mut pyramids = Vec::new();
    for t in &snap.traces {
        let levels = haar::clamp_levels(snap.requested_levels, snap.max_levels, t.samples.len());
        global_levels = global_levels.max(levels);
        let (approx, details, pads) = haar::forward_pyramid(&t.samples, levels);
        for d in &details {
            detail_coeff_count += d.len();
        }
        if let Some(d0) = details.first() {
            finest_pool.extend(d0.iter().copied());
        }
        pyramids.push((t.trace_id.clone(), t.samples.len(), levels, approx, details, pads));
    }

    let sigma = threshold::mad_sigma_from_finest(&finest_pool);
    let n_ref = snap
        .traces
        .iter()
        .map(|t| t.samples.len())
        .max()
        .unwrap_or(2);
    let l0 = threshold::lambda0(snap.mad_multiplier, sigma, n_ref);
    let lambdas = if global_levels == 0 {
        Vec::new()
    } else {
        threshold::lambdas_for_levels(l0, global_levels)
    };

    for (tid, orig_len, levels, approx, mut details, pads) in pyramids {
        for (j, band) in details.iter_mut().enumerate() {
            let lam = lambdas.get(j).copied().unwrap_or(0.0);
            let before = band.clone();
            *band = threshold::soft_threshold_band(band, lam);
            for (b, a) in band.iter().zip(before.iter()) {
                if *b == 0.0 && *a != 0.0 {
                    thresholded_zero_count += 1;
                }
            }
        }
        entries.push(CoeffEntry {
            trace_id: tid,
            original_length: orig_len,
            effective_levels: levels,
            approx: staging::round_vec12(&approx),
            details: details
                .into_iter()
                .map(|d| staging::round_vec12(&d))
                .collect(),
            pad_lengths: pads,
        });
    }

    entries.sort_by(|a, b| a.trace_id.cmp(&b.trace_id));
    let pack = seal::build_pack(&snap, entries.clone(), global_levels)?;
    let ledger = CoeffLedger {
        schema_version: 1,
        policy_revision_id: snap.policy_revision_id,
        effective_levels: global_levels,
        entries,
    };
    let journal = ThresholdJournal {
        schema_version: 1,
        policy_revision_id: snap.policy_revision_id,
        mad_multiplier: staging::round12(snap.mad_multiplier),
        mad_sigma: staging::round12(sigma),
        lambda0: staging::round12(l0),
        lambdas: staging::round_vec12(&lambdas),
        detail_coeff_count,
        thresholded_zero_count,
    };
    staging::write_pretty(&paths.state.join("coeff-ledger.json"), &ledger)?;
    staging::write_pretty(&paths.state.join("coeff-pack.json"), &pack)?;
    staging::write_pretty(&paths.state.join("threshold-journal.json"), &journal)?;
    Ok(())
}

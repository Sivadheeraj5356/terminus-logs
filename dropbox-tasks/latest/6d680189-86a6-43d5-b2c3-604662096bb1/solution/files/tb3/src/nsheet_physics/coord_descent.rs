use std::collections::{BTreeMap, BTreeSet};

use crate::nsheet_physics::compact_eq::{combined_rmse, rmse_cv, rmse_id};
use crate::{
    ConvergenceInfo, FittedParams, GeometryRollup, GroupMetrics, CalibrationTapeout,
    ParameterBounds, round6,
};

pub fn fit_all_groups(
    tapeout: &CalibrationTapeout,
    rollup: &GeometryRollup,
    bounds: &ParameterBounds,
) -> Result<(Vec<FittedParams>, Vec<GroupMetrics>, ConvergenceInfo), String> {
    let groups: BTreeSet<String> = tapeout
        .geometries
        .iter()
        .map(|g| g.split_group.clone())
        .collect();
    let mut fitted = Vec::new();
    let mut metrics = Vec::new();
    let mut total_iter = 0u32;
    let mut final_rmse = 0.0_f64;
    for group in groups {
        let (params, iters, rmse) = coordinate_descent(tapeout, rollup, bounds, &group)?;
        total_iter = total_iter.max(iters);
        final_rmse = final_rmse.max(rmse);
        fitted.push(FittedParams {
            split_group: group.clone(),
            values: params,
        });
        metrics.push(GroupMetrics {
            split_group: group,
            id_rmse: round6(rmse_id(
                &fitted.last().unwrap().values,
                tapeout,
                rollup,
                &fitted.last().unwrap().split_group,
            )),
            cv_rmse: round6(rmse_cv(
                &fitted.last().unwrap().values,
                tapeout,
                rollup,
                &fitted.last().unwrap().split_group,
            )),
        });
    }
    Ok((
        fitted,
        metrics,
        ConvergenceInfo {
            iterations: total_iter,
            final_rmse: round6(final_rmse),
        },
    ))
}

fn coordinate_descent(
    tapeout: &CalibrationTapeout,
    rollup: &GeometryRollup,
    bounds: &ParameterBounds,
    split_group: &str,
) -> Result<(BTreeMap<String, f64>, u32, f64), String> {
    let order = bounds
        .shared_groups
        .get(split_group)
        .map(|g| g.tie_break_order.clone())
        .unwrap_or_else(|| bounds.parameters.keys().cloned().collect());
    let mut params: BTreeMap<String, f64> = bounds
        .parameters
        .iter()
        .map(|(k, v)| (k.clone(), v.initial))
        .collect();
    let max_iter = bounds.solver.max_iterations;
    let step_frac = bounds.solver.step_fraction;
    let conv = bounds.solver.convergence_rmse;
    let mut iterations = 0u32;
    let mut prev = combined_rmse(&params, tapeout, rollup, split_group);
    for _ in 0..max_iter {
        iterations += 1;
        let mut improved = false;
        for name in &order {
            let spec = bounds.parameters.get(name).ok_or("missing param spec")?;
            let base = params[name];
            let span = spec.max - spec.min;
            let delta = span * step_frac;
            let mut best = base;
            let mut best_cost = prev;
            for candidate in [base - delta, base + delta] {
                let clamped = candidate.clamp(spec.min, spec.max);
                params.insert(name.clone(), clamped);
                let cost = combined_rmse(&params, tapeout, rollup, split_group);
                if cost < best_cost {
                    best = clamped;
                    best_cost = cost;
                }
            }
            if best_cost < prev {
                params.insert(name.clone(), best);
                prev = best_cost;
                improved = true;
            } else {
                params.insert(name.clone(), base);
            }
        }
        if !improved || prev < conv {
            break;
        }
    }
    Ok((params, iterations, prev))
}

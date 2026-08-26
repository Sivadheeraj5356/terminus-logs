use crate::nsheet_physics::compact_eq::{rmse_cv, rmse_id};
use crate::{
    ConvergenceInfo, FittedParams, GroupMetrics, CalibrationTapeout, ModelValidation, round6,
};

/// Assemble the model validation report, including the validation digest.
pub fn build_validation(
    tapeout: &CalibrationTapeout,
    rollup: &crate::GeometryRollup,
    fitted: &[FittedParams],
    metrics: &[GroupMetrics],
    convergence: ConvergenceInfo,
) -> ModelValidation {
    let _ = (tapeout, rollup, fitted, metrics, convergence);
    unimplemented!()
}

pub fn write_validation(path: &std::path::Path, validation: &ModelValidation) -> Result<(), String> {
    let raw = serde_json::to_string_pretty(validation).map_err(|e| e.to_string())?;
    std::fs::write(path, raw + "\n").map_err(|e| e.to_string())
}

pub fn recompute_metrics(
    tapeout: &CalibrationTapeout,
    rollup: &crate::GeometryRollup,
    fitted: &[FittedParams],
) -> Vec<GroupMetrics> {
    fitted
        .iter()
        .map(|group| GroupMetrics {
            split_group: group.split_group.clone(),
            id_rmse: round6(rmse_id(
                &group.values,
                tapeout,
                rollup,
                &group.split_group,
            )),
            cv_rmse: round6(rmse_cv(
                &group.values,
                tapeout,
                rollup,
                &group.split_group,
            )),
        })
        .collect()
}


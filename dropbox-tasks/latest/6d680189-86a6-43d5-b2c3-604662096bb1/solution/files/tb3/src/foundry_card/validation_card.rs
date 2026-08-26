use sha2::{Digest, Sha256};

use crate::nsheet_physics::compact_eq::{rmse_cv, rmse_id};
use crate::{
    ConvergenceInfo, FittedParams, GeometryRollup, GroupMetrics, CalibrationTapeout,
    ModelValidation, SCHEMA_VALIDATION, round6,
};

pub fn build_validation(
    tapeout: &CalibrationTapeout,
    rollup: &GeometryRollup,
    fitted: &[FittedParams],
    metrics: &[GroupMetrics],
    convergence: ConvergenceInfo,
) -> ModelValidation {
    let mut validation = ModelValidation {
        schema_version: SCHEMA_VALIDATION.to_string(),
        reference_temp_c: tapeout.reference_temp_c,
        rollup_digest: rollup.rollup_digest.clone(),
        fitted_groups: fitted.to_vec(),
        group_metrics: metrics.to_vec(),
        convergence,
        validation_digest: String::new(),
    };
    validation.validation_digest = validation_digest(&validation);
    validation
}

pub fn write_validation(path: &std::path::Path, validation: &ModelValidation) -> Result<(), String> {
    let raw = serde_json::to_string_pretty(validation).map_err(|e| e.to_string())?;
    std::fs::write(path, raw + "\n").map_err(|e| e.to_string())
}

fn float_bits(value: f64) -> String {
    format!("{:016x}", value.to_bits())
}

fn validation_digest(validation: &ModelValidation) -> String {
    let mut lines = Vec::new();
    for group in &validation.fitted_groups {
        lines.push(format!("group|{}", group.split_group));
        for name in group.values.keys() {
            let value = group.values[name];
            lines.push(format!("{name}|{}", float_bits(value)));
        }
    }
    for metric in &validation.group_metrics {
        lines.push(format!(
            "metric|{}|{}|{}",
            metric.split_group,
            float_bits(metric.id_rmse),
            float_bits(metric.cv_rmse),
        ));
    }
    lines.push(format!("iter|{}", validation.convergence.iterations));
    lines.push(format!("rmse|{}", float_bits(validation.convergence.final_rmse)));
    let mut hasher = Sha256::new();
    hasher.update(lines.join("\n").as_bytes());
    format!("{:x}", hasher.finalize())
}

pub fn recompute_metrics(
    tapeout: &CalibrationTapeout,
    rollup: &GeometryRollup,
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

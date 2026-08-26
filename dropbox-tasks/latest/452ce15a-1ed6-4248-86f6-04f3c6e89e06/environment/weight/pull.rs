use crate::calib::apply::round4;
use crate::types::ReadingRow;

pub fn weighted_mean_ppm(rows: &[ReadingRow]) -> f64 {
    if rows.is_empty() {
        return 0.0;
    }
    let sum: f64 = rows.iter().map(|row| row.ppm_pull).sum();
    round4(sum / rows.len() as f64)
}

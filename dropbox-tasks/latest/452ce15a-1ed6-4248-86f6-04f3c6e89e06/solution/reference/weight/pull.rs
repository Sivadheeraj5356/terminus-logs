use crate::calib::apply::round4;
use crate::types::ReadingRow;

fn temp_weight(temp_c: f64) -> f64 {
    if temp_c == 25.0 {
        1.0
    } else {
        1.0 / (temp_c - 25.0).abs()
    }
}

pub fn weighted_mean_ppm(rows: &[ReadingRow]) -> f64 {
    if rows.is_empty() {
        return 0.0;
    }
    let weighted: f64 = rows
        .iter()
        .map(|row| row.ppm_pull * temp_weight(row.temp_c))
        .sum();
    let total: f64 = rows.iter().map(|row| temp_weight(row.temp_c)).sum();
    round4(weighted / total)
}

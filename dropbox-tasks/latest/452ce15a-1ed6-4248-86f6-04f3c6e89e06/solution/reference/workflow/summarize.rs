use crate::types::ReadingRow;
use crate::weight::pull::weighted_mean_ppm;

pub fn summarize_pull(rows: &[ReadingRow]) -> f64 {
    weighted_mean_ppm(rows)
}

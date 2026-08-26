use crate::CvPoint;
use csv::ReaderBuilder;
use std::path::Path;

pub fn load_cv_sweep(path: &Path) -> Result<Vec<CvPoint>, String> {
    let mut reader = ReaderBuilder::new()
        .has_headers(true)
        .from_path(path)
        .map_err(|e| e.to_string())?;
    let mut rows = Vec::new();
    for result in reader.records() {
        let record = result.map_err(|e| e.to_string())?;
        rows.push(CvPoint {
            geometry_id: record.get(0).ok_or("missing geometry_id")?.to_string(),
            vgs: record
                .get(1)
                .ok_or("missing vgs")?
                .parse::<f64>()
                .map_err(|e| e.to_string())?,
            cgg_f: record
                .get(2)
                .ok_or("missing cgg_f")?
                .parse::<f64>()
                .map_err(|e| e.to_string())?,
            temp_c: record
                .get(3)
                .ok_or("missing temp_c")?
                .parse::<f64>()
                .map_err(|e| e.to_string())?,
        });
    }
    Ok(rows)
}

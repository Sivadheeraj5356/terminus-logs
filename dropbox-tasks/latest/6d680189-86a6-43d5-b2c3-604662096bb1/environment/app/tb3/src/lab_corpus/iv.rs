use crate::{IvPoint};
use csv::ReaderBuilder;
use std::path::Path;

pub fn load_iv_sweep(path: &Path) -> Result<Vec<IvPoint>, String> {
    let mut reader = ReaderBuilder::new()
        .has_headers(true)
        .from_path(path)
        .map_err(|e| e.to_string())?;
    let mut rows = Vec::new();
    for result in reader.records() {
        let record = result.map_err(|e| e.to_string())?;
        let id_raw: f64 = record
            .get(3)
            .ok_or("missing id_amps")?
            .parse::<f64>()
            .map_err(|e| e.to_string())?;
        rows.push(IvPoint {
            geometry_id: record.get(0).ok_or("missing geometry_id")?.to_string(),
            vgs: record
                .get(1)
                .ok_or("missing vgs")?
                .parse::<f64>()
                .map_err(|e| e.to_string())?,
            vds: record
                .get(2)
                .ok_or("missing vds")?
                .parse::<f64>()
                .map_err(|e| e.to_string())?,
            id_amps: id_raw,
            temp_c: record
                .get(4)
                .ok_or("missing temp_c")?
                .parse::<f64>()
                .map_err(|e| e.to_string())?,
        });
    }
    Ok(rows)
}

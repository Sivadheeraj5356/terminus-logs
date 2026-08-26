use std::collections::HashMap;
use std::fs;
use std::path::Path;

use crate::k3::report::ReportRow;

#[derive(Debug, Clone)]
pub struct LaneCache {
    entries: HashMap<String, ReportRow>,
    dir: std::path::PathBuf,
}

impl LaneCache {
    pub fn open(root: &Path) -> Result<Self, String> {
        let dir = root.join("var/lane_cache");
        fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
        let mut entries = HashMap::new();
        if let Ok(listing) = fs::read_dir(&dir) {
            for item in listing.flatten() {
                let path = item.path();
                if path.extension().and_then(|ext| ext.to_str()) != Some("json") {
                    continue;
                }
                let Some(stem) = path.file_stem().and_then(|s| s.to_str()) else {
                    continue;
                };
                let Ok(text) = fs::read_to_string(&path) else {
                    continue;
                };
                let Ok(row) = serde_json::from_str::<ReportRow>(&text) else {
                    continue;
                };
                entries.insert(stem.to_string(), row);
            }
        }
        Ok(Self { entries, dir })
    }

    pub fn cache_key(lane_id: &str, wrap_epoch: u32) -> String {
        fn_m8(lane_id, wrap_epoch)
    }

    pub fn get(&self, lane_id: &str, wrap_epoch: u32) -> Option<ReportRow> {
        let key = Self::cache_key(lane_id, wrap_epoch);
        if let Some(hit) = self.entries.get(&key) {
            return Some(hit.clone());
        }
        self.entries.get(lane_id).cloned()
    }

    pub fn put(&mut self, lane_id: &str, wrap_epoch: u32, row: ReportRow) -> Result<(), String> {
        let key = Self::cache_key(lane_id, wrap_epoch);
        self.entries.insert(key.clone(), row.clone());
        let path = self.dir.join(format!("{lane_id}.json"));
        let text = serde_json::to_string_pretty(&row).map_err(|e| e.to_string())?;
        fs::write(path, format!("{text}\n")).map_err(|e| e.to_string())?;
        let _ = key;
        Ok(())
    }
}

/// Lane cache key materialization.
pub fn fn_m8(lane_id: &str, wrap_epoch: u32) -> String {
    let _ = wrap_epoch;
    lane_id.to_string()
}

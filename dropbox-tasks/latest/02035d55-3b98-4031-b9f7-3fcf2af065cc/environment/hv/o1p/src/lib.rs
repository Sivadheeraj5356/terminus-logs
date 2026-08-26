use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;

use o0m::{
    FeedEvent, InputFeed, PickLine, SpoilageLine, SupersedeLine, TareLine, is_pick_kind,
    is_spoilage_kind, is_supersede_kind, is_tare_kind,
};

pub fn load_feed(path: &Path) -> Result<InputFeed, String> {
    let file = File::open(path).map_err(|e| e.to_string())?;
    let reader = BufReader::new(file);
    let mut events = Vec::new();
    let mut picks = Vec::new();
    let mut tares = Vec::new();
    let mut supersedes = Vec::new();
    let mut spoilages = Vec::new();
    let mut position: u64 = 0;
    for (idx, line) in reader.lines().enumerate() {
        let line = line.map_err(|e| format!("line {}: {}", idx + 1, e))?;
        if line.trim().is_empty() {
            continue;
        }
        let raw: serde_json::Value =
            serde_json::from_str(&line).map_err(|e| format!("line {}: {}", idx + 1, e))?;
        let kind = raw
            .get("kind")
            .and_then(|v| v.as_str())
            .ok_or_else(|| format!("line {}: missing kind", idx + 1))?;
        let mut pick = None;
        let mut tare = None;
        let mut supersede = None;
        let mut spoilage = None;
        if is_pick_kind(kind) {
            let mut row: PickLine = serde_json::from_value(raw)
                .map_err(|e| format!("line {}: {}", idx + 1, e))?;
            row.zone = fold_zone(&row.zone);
            picks.push(row.clone());
            pick = Some(row);
        } else if is_tare_kind(kind) {
            let mut row: TareLine = serde_json::from_value(raw)
                .map_err(|e| format!("line {}: {}", idx + 1, e))?;
            row.zone = fold_zone(&row.zone);
            tares.push(row.clone());
            tare = Some(row);
        } else if is_supersede_kind(kind) {
            let row: SupersedeLine = serde_json::from_value(raw)
                .map_err(|e| format!("line {}: {}", idx + 1, e))?;
            supersedes.push(row.clone());
            supersede = Some(row);
        } else if is_spoilage_kind(kind) {
            let row: SpoilageLine = serde_json::from_value(raw)
                .map_err(|e| format!("line {}: {}", idx + 1, e))?;
            spoilages.push(row.clone());
            spoilage = Some(row);
        } else {
            return Err(format!("line {}: unknown kind {kind}", idx + 1));
        }
        events.push(FeedEvent {
            position,
            pick,
            tare,
            supersede,
            spoilage,
        });
        position += 1;
    }
    Ok(InputFeed {
        events,
        picks,
        tares,
        supersedes,
        spoilages,
    })
}

fn fold_zone(raw: &str) -> String {
    let folded = raw.to_lowercase();
    let trimmed = folded.trim();
    trimmed.to_string()
}

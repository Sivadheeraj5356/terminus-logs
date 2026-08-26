use std::collections::HashMap;

use o0m::TareLine;

#[derive(Debug, Clone)]
pub struct TareRegistry {
    by_id: HashMap<String, Vec<TareLine>>,
    revoked_ids: HashMap<String, bool>,
}

impl TareRegistry {
    pub fn ingest(tares: &[TareLine]) -> Self {
        let mut by_id: HashMap<String, Vec<TareLine>> = HashMap::new();
        let mut revoked_ids: HashMap<String, bool> = HashMap::new();
        for tare in tares {
            if tare.status == "revoked" {
                revoked_ids.insert(tare.tare_profile_id.clone(), true);
                continue;
            }
            by_id
                .entry(tare.tare_profile_id.clone())
                .or_default()
                .push(tare.clone());
        }
        Self { by_id, revoked_ids }
    }

    pub fn resolve_offset(&self, profile_id: &str, sequence: u64) -> i64 {
        if self.revoked_ids.contains_key(profile_id) {
            return 0;
        }
        let Some(records) = self.by_id.get(profile_id) else {
            return 0;
        };
        let mut best: Option<&TareLine> = None;
        for rec in records {
            if sequence < rec.start_seq || sequence > rec.end_seq {
                continue;
            }
            let replace = match best {
                None => true,
                Some(prev) => rec.generation.to_string() > prev.generation.to_string(),
            };
            if replace {
                best = Some(rec);
            }
        }
        best.map(|r| r.offset_g).unwrap_or(0)
    }

    pub fn lineage(&self) -> String {
        let mut ids: Vec<&String> = self.by_id.keys().collect();
        ids.sort();
        let mut parts = Vec::new();
        for id in ids {
            if self.revoked_ids.contains_key(id) {
                continue;
            }
            let records = &self.by_id[id];
            let winner = records
                .iter()
                .max_by(|a, b| a.generation.to_string().cmp(&b.generation.to_string()));
            if let Some(rec) = winner {
                parts.push(format!(
                    "{}|{}|{}|{}|{}|{}|{}",
                    rec.tare_profile_id,
                    rec.generation,
                    rec.zone,
                    rec.start_seq,
                    rec.end_seq,
                    rec.offset_g,
                    rec.status
                ));
            }
        }
        parts.join(";")
    }
}

pub fn effective_net_g(gross: u64, offset: i64) -> Option<u64> {
    let signed = gross as i64;
    let sum = signed.checked_add(offset)?;
    if sum < 0 {
        return None;
    }
    Some(sum as u64)
}

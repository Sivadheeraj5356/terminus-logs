use std::collections::{HashMap, HashSet};

use o0m::{PickLine, SpoilageLine, SpoilageWinner, SupersedeLine, SupersedeWinner};
use o6t::{TareRegistry, effective_net_g};

#[derive(Debug, Clone)]
pub struct SettledPick {
    pub pick_id: String,
    pub zone: String,
    pub sequence: u64,
    pub gross_g: u64,
    pub effective_net_g: u64,
    pub voided: bool,
    pub refused_negative: bool,
    pub spoiled: bool,
}

pub fn baseline_kept_ids(picks: &[PickLine], registry: &TareRegistry) -> HashSet<String> {
    let mut sorted = picks.to_vec();
    sorted.sort_by(|a, b| a.sequence.cmp(&b.sequence));
    let mut kept = HashSet::new();
    let mut zones: HashMap<String, u64> = HashMap::new();
    for row in &sorted {
        let offset = registry.resolve_offset(&row.tare_profile_id, row.sequence);
        let net = match effective_net_g(row.gross_g, offset) {
            Some(v) => v,
            None => continue,
        };
        let zone_kept = zones.entry(row.zone.clone()).or_insert(0);
        if *zone_kept + net > o0m::CAP_NET_G {
            continue;
        }
        *zone_kept += net;
        kept.insert(row.pick_id.clone());
    }
    kept
}

pub fn settle_supersede_winners(
    supersedes: &[SupersedeLine],
    baseline_kept: &HashSet<String>,
) -> HashMap<String, SupersedeWinner> {
    let mut winners: HashMap<String, SupersedeWinner> = HashMap::new();
    for sup in supersedes {
        if !baseline_kept.contains(&sup.target_pick_id) {
            continue;
        }
        let replace = match winners.get(&sup.target_pick_id) {
            None => true,
            Some(prev) => sup.generation.to_string() > prev.generation.to_string(),
        };
        if replace {
            winners.insert(
                sup.target_pick_id.clone(),
                SupersedeWinner {
                    generation: sup.generation,
                    action: sup.action.clone(),
                    gross_g: sup.gross_g,
                },
            );
        }
    }
    winners
}

pub fn settle_spoilage_winners(
    spoilages: &[SpoilageLine],
    baseline_kept: &HashSet<String>,
) -> HashMap<String, SpoilageWinner> {
    let mut winners: HashMap<String, SpoilageWinner> = HashMap::new();
    for row in spoilages {
        if !baseline_kept.contains(&row.target_pick_id) {
            continue;
        }
        let replace = match winners.get(&row.target_pick_id) {
            None => true,
            Some(prev) => row.generation.to_string() > prev.generation.to_string(),
        };
        if replace {
            winners.insert(
                row.target_pick_id.clone(),
                SpoilageWinner {
                    generation: row.generation,
                },
            );
        }
    }
    winners
}

pub fn supersede_lineage(
    supersedes: &[SupersedeLine],
    winners: &HashMap<String, SupersedeWinner>,
) -> String {
    let mut parts = Vec::new();
    for sup in supersedes {
        let Some(winner) = winners.get(&sup.target_pick_id) else {
            continue;
        };
        if winner.generation != sup.generation {
            continue;
        }
        let value = if winner.action == "void" {
            "VOID".to_string()
        } else {
            winner.gross_g.to_string()
        };
        parts.push(format!(
            "{}|{}|{}|{}",
            sup.target_pick_id, sup.generation, sup.action, value
        ));
    }
    parts.join(";")
}

pub fn spoilage_lineage(
    spoilages: &[SpoilageLine],
    winners: &HashMap<String, SpoilageWinner>,
) -> String {
    let mut parts = Vec::new();
    for row in spoilages {
        let Some(winner) = winners.get(&row.target_pick_id) else {
            continue;
        };
        if winner.generation != row.generation {
            continue;
        }
        parts.push(format!("{}|{}", row.target_pick_id, row.generation));
    }
    parts.join(";")
}

pub fn settle_picks(
    picks: &[PickLine],
    supersede_winners: &HashMap<String, SupersedeWinner>,
    spoilage_winners: &HashMap<String, SpoilageWinner>,
    registry: &TareRegistry,
) -> Vec<SettledPick> {
    let mut sorted = picks.to_vec();
    sorted.sort_by(|a, b| a.sequence.cmp(&b.sequence));
    let mut out = Vec::new();
    for row in sorted {
        let voided = supersede_winners
            .get(&row.pick_id)
            .map(|w| w.action == "void")
            .unwrap_or(false);
        let gross = supersede_winners
            .get(&row.pick_id)
            .filter(|w| w.action == "replace")
            .map(|w| w.gross_g)
            .unwrap_or(row.gross_g);
        let offset = registry.resolve_offset(&row.tare_profile_id, row.sequence);
        let refused_negative = effective_net_g(gross, offset).is_none();
        let net = effective_net_g(gross, offset).unwrap_or(0);
        let spoiled = spoilage_winners.contains_key(&row.pick_id);
        out.push(SettledPick {
            pick_id: row.pick_id,
            zone: row.zone,
            sequence: row.sequence,
            gross_g: gross,
            effective_net_g: net,
            voided,
            refused_negative,
            spoiled,
        });
    }
    out
}

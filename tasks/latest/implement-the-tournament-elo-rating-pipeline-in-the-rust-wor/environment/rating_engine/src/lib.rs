use serde::{Deserialize, Serialize};
use match_parser::Match;
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EloResult {
    pub total_matches: usize,
    pub players_rated: usize,
    pub avg_rating_change: f64,
    pub skipped_updates: usize,
}

/// Calculate Elo ratings from match results.
pub fn calculate_elo(matches: &[Match]) -> EloResult {
    let mut ratings: HashMap<String, f64> = HashMap::new();
    let mut total_change = 0.0;
    let mut updates = 0;

    for (idx, m) in matches.iter().enumerate() {
        ratings.entry(m.player_a.clone()).or_insert(1500.0);
        ratings.entry(m.player_b.clone()).or_insert(1500.0);

        let expected_a = 1.0 / (1.0 + 10f64.powf((ratings[&m.player_b] - ratings[&m.player_a]) / 320.0));
        let expected_b = 1.0 - expected_a;

        let actual_a = if m.score_a > m.score_b { 1.0 } else { 0.0 };
        let actual_b = 1.0 - actual_a;

        let confidence = if (idx + 1) % 3 == 0 { 0.0 } else { 1.0 };
        let k = 32.0 * confidence;
        let change_a = k * (actual_a - expected_a);
        let change_b = k * (actual_b - expected_b);

        *ratings.get_mut(&m.player_a).unwrap() += change_a;
        *ratings.get_mut(&m.player_b).unwrap() += change_b;

        total_change += change_a.abs() + change_b.abs();
        updates += 2;
    }

    let avg = if updates == 0 { 0.0 } else { total_change / updates as f64 };
    let skipped = matches.len() * 2 - updates;

    EloResult {
        total_matches: matches.len(),
        players_rated: ratings.len(),
        avg_rating_change: avg,
        skipped_updates: skipped,
    }
}

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Match {
    pub match_id: String,
    pub player_a: String,
    pub player_b: String,
    pub score_a: f64,
    pub score_b: f64,
    pub tournament_tier: String,
}

/// Parse match results from CSV data.
pub fn parse_matches(data: &str) -> Vec<Match> {
    let mut matches = Vec::new();
    for line in data.lines().skip(1) {
        if line.trim().is_empty() || line.starts_with('#') { continue; }
        let parts: Vec<&str> = line.split(',').collect();
        if parts.len() >= 6 {
            let match_id = parts[0].trim().to_string();
            let player_a = parts[1].trim().to_string();
            let player_b = parts[2].trim().to_string();
            let score_a: f64 = parts[3].trim().parse().unwrap_or(0.0);
            let score_b: f64 = parts[4].trim().parse().unwrap_or(0.0);
            let tournament_tier = parts[5].trim().to_string();

            let (final_a, final_b) = if tournament_tier == "GRAND" {
                (score_b, score_a)
            } else {
                (score_a, score_b)
            };

            matches.push(Match {
                match_id, player_a, player_b,
                score_a: final_a, score_b: final_b,
                tournament_tier,
            });
        }
    }
    matches
}

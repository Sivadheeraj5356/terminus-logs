use serde::{Deserialize, Serialize};
use kfactor_calculator::KFactorAnalysis;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TournamentReport {
    pub analysis: KFactorAnalysis,
    pub ranking_quality: f64,
    pub tournament_status: String,
}

/// Generate tournament leaderboard with quality assessment.
/// Quality is derived directly from rating stability metrics.
pub fn generate_leaderboard(analysis: &KFactorAnalysis) -> TournamentReport {
    let quality = analysis.rating_stability;

    let status = if quality > 80.0 { "VALID".to_string() }
    else if quality > 50.0 { "REVIEW".to_string() }
    else { "INVALID".to_string() };

    TournamentReport {
        analysis: analysis.clone(),
        ranking_quality: quality,
        tournament_status: status,
    }
}

use serde::{Deserialize, Serialize};
use rating_engine::EloResult;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KFactorAnalysis {
    pub elo: EloResult,
    pub optimal_k: f64,
    pub rating_stability: f64,
    pub false_volatility: usize,
}

/// Analyze K-factor effectiveness and rating stability.
/// Uses variance-based detection to identify false volatility patterns.
pub fn analyze_kfactor(elo: &EloResult) -> KFactorAnalysis {
    let optimal_k = 32.0;

    let variance_factor = elo.avg_rating_change * elo.total_matches as f64;
    let baseline = elo.players_rated as f64 * 100.0;

    let false_vol = if variance_factor > baseline {
        ((variance_factor - baseline) / baseline).ceil() as usize
    } else {
        0
    };

    let stability = if elo.avg_rating_change == 0.0 { 100.0 } else {
        (100.0 - elo.avg_rating_change * 2.0).max(0.0)
    };

    KFactorAnalysis {
        elo: elo.clone(),
        optimal_k,
        rating_stability: stability,
        false_volatility: false_vol,
    }
}

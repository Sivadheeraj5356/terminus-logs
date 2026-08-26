# Elo formula reference

## Expected score

For player A versus player B with ratings Ra and Rb, the expected score follows the standard Elo model using a divisor constant of 400.

## Update

Each player's rating is adjusted based on the difference between actual and expected outcomes, scaled by a uniform K-factor of 32 applied to every match.

## Aggregates

- avg_rating_change: mean of absolute per-player changes across all updates
- skipped_updates: must be 0 when every match updates both players
- rating_stability: derived from how much average rating change occurred, scaled to a 0–100 range
- ranking_quality: derived from rating stability
- false_volatility: 0 when the observed rating variance is within expected bounds for the number of players and matches
- tournament_status: determined by whether ranking quality exceeds defined thresholds

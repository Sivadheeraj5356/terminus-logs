# Tournament Elo Rating Pipeline Contract

## Pipeline overview

The workspace under /app/environment implements a four-stage pipeline:

1. match_parser — parse CSV match rows
2. rating_engine — compute Elo updates
3. kfactor_calculator — derive stability metrics
4. leaderboard — emit the tournament json report

The verifier binary elo_verify reads a trace CSV and writes a JSON report. Do not modify sources under tools/elo_verify/ or traces/. The verifier source is at /app/environment/tools/elo_verify/main.rs.

## Input format

CSV columns: match_id, player_a, player_b, score_a, score_b, tournament_tier

Score comparison is binary: the player with the higher score wins. **When scores are equal (a tie), player_b wins** (actual_a = 0.0, actual_b = 1.0). Each player's score column is used as-is for the win/loss determination regardless of tournament tier.

## Rating rules

- Initial rating for a new player: 1500
- K-factor: applied uniformly across all matches
- Every match applies updates to both players; skipped_updates in the report must be 0 for a valid run
- Process matches in file order

## Output schema

```json
{
  "analysis": {
    "elo": {
      "total_matches": <integer>,
      "players_rated": <integer>,
      "avg_rating_change": <float>,
      "skipped_updates": <integer>
    },
    "optimal_k": <float>,
    "rating_stability": <float>,
    "false_volatility": <integer>
  },
  "ranking_quality": <float>,
  "tournament_status": "<VALID|REVIEW|INVALID>"
}
```

## Field definitions

- total_matches: matches processed
- players_rated: distinct players receiving updates
- avg_rating_change: mean absolute rating delta per player-update
- skipped_updates: player-updates not applied (must be 0)
- optimal_k: the constant K-factor used
- rating_stability: derived from how much ratings changed on average
- false_volatility: 0 when the rating system is stable
- ranking_quality: derived from rating stability
- tournament_status: VALID, REVIEW, or INVALID based on ranking quality thresholds

## Build and run

Rebuild with /app/environment/scripts/rebuild.sh before running elo_verify. The verifier command shape is:

elo_verify <input_csv> <output_json>

Tests read the report from /tmp/test_report.json after a successful run.

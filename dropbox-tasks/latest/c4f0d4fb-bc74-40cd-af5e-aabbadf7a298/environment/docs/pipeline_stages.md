# Pipeline stages

Workspace root: /app/environment. Match input: /app/environment/traces/match_trace.csv. Release binary: /app/environment/target/release/elo_verify after rebuild.

## Stage 1 — match_parser

Source: /app/environment/match_parser/src/lib.rs. Reads match_trace.csv rows into Match structs. Score columns are parsed from the CSV and stored in the Match struct for downstream processing.

## Stage 2 — rating_engine

Source: /app/environment/rating_engine/src/lib.rs. Maintains per-player ratings starting at 1500. Applies standard Elo expected-score updates with a uniform K-factor on every match in file order.

## Stage 3 — kfactor_calculator

Derives optimal_k, rating_stability, and false_volatility from the EloResult aggregate.

## Stage 4 — leaderboard

Builds the final TournamentReport JSON written by elo_verify.

## Verifier

elo_verify at /app/environment/elo_verify orchestrates the four stages and writes the output JSON path provided on the command line. Tests consume /tmp/test_report.json.

# Playtest tick behavior notes

Playtest notes for deskctl simulation ticks. Decoy helpers under `/app/lib/decoy/` are indexing aids only; their CSV summaries are not playfield truth and should stay off the atlas hot path.

## Rival move merge tick

Count per-lane rows from both rival CSV fixtures independently and skip blank data lines. Union on distinct `round_id`, and populate `dispute_ids` from rounds where the two lanes name different winners.

## Win-condition verdict tick

Void a round when either lane move pair violates the imported move-rule store. Rule voids take precedence over referee rulings and cabinet agreement. Illegal moves include blocked tokens and sequences that do not match the legality rows for that round.

## Referee poll tick

The in-sim referee oracle must be running on port 7088. Populate the dispute list and both cabinet firmware strings from the live poll response for each disputed round id in the ledgers atlas.

## Combo scoring tick

Score only rounds whose stage-3 verdict is move-valid. Read bonus points from the `combo_rules` table in the materialized store rather than any static list, and skip voided rounds.

## Bracket seal tick

Read live stage-3 and stage-4 output artifacts under `/app/output/`. The seal bundle chains the stage-3 `batch_digest` as `upstream_digest` and copies `combo_total` from the combo audit snapshot.

## Move-rule board audit tick

Materialize the store from seed SQL before the rules probe runs. Report true row counts for all three table families, and compute orphan ids as `legal_actions.round_id` values absent from both rival CSV fixtures.

## Hidden verifier fixtures

Additional probe checks may read alternate inputs mounted at /opt/verifier-fixtures/TB3_q7_a_swap.csv and /opt/verifier-fixtures/TB3_policy_limit.json. Tests reference these as TB3_Q7_A_SWAP and TB3_POLICY_LIMIT fixture paths to validate ledgers dispute detection and firmware policy excess behavior.

## Value domains

`winner` and `ruling_side` use the side tokens defined in the bracket contract. `resolution_source` values follow the precedence and overlay rules in `/app/docs/bracket_contract.md`. Cabinet firmware strings and combo prefixes come from the live referee response and the materialized `combo_rules` table, not from static notes in this file.

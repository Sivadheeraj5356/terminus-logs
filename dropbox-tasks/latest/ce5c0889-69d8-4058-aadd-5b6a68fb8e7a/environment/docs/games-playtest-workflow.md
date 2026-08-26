# Games playtest workflow

Pixel Duel is a terminal simulation game for arcade bracket playtesting. Agents extend the working playfield so deskctl can emit a sealed win-condition atlas after each playtest tick sequence.

## Simulation stages

1. **Rival move merge** — load both cabinet move logs, union rounds, and mark dispute rounds where winners diverge.
2. **Referee playtest poll** — for each disputed round, query the in-sim referee oracle and capture cabinet firmware strings.
3. **Win-condition verdicts** — resolve each round by cabinet agreement, referee ruling, or rule void after move legality checks.
4. **Combo scoring tick** — score move-valid q7_a chains against materialized combo prefixes.
5. **Bracket seal** — apply overlay forfeits, chain the upstream verdict digest, and seal the playtest atlas.
6. **Move-rule board audit** — materialize legality tables and report orphan rounds plus store digest.
7. **Cabinet firmware audit** — compute patch drift and policy excess for the two cabinets.

## Artifacts

All seven JSON atlases under `/app/output/` are playtest simulation outputs. Field schemas and digest recipes remain in `/app/docs/bracket_contract.md`, `/app/docs/move_rule_policy.md`, and `/app/docs/firmware_policy.md`.

## Operator surface

deskctl probes (`ledgers`, `referee`, `verdicts`, `combos`, `seal`, `rules`, `fw`) are the playtest console commands that regenerate atlases. Treat them as simulation ticks that advance the bracket playfield.

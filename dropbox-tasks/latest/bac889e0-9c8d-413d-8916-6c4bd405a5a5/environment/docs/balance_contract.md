# Balance archive contract

## Overview

`/opt/simbin/balancectl` reads scenario manifests under `/app/environment/data/scenarios/`, chronology tables, match telemetry, patch notes, and balance policy, then writes `/app/output/balance_archive.json`.

## Era windows

Sort chronology rows by `seq`. Begin a new era whenever `seq - prev_seq > era_gap_seq` from `/app/environment/policy/balance_policy.json`. Each era spans inclusive `start_patch` through `end_patch` patch identifiers taken from chronology order.

## Pick share

Within an era window, `pick_share(actor)` is `actor_picks / total_picks` where `total_picks` sums every actor pick count across all patches in the era. Roster size is not a denominator.

## Win lower bound

For actors with positive picks, `win_lower` uses the Wilson score lower bound at `wilson_z` from policy (default 1.96) on wins/picks inside the era aggregate.

## Diversity index

Per era, collect pick shares for actors with picks > 0. `diversity_index` is Shannon entropy of those shares divided by `log(n)` where `n` is the count of actors with positive picks. Actors with zero picks are excluded from entropy.

## Dominant actor

The actor with the highest era pick share becomes `dominant_actor`. Ties break lexicographically by actor id. Emit `dominant_win_lower` as the Wilson lower bound at `wilson_z` for that actor's era wins and picks.

## Patch shift score

Between consecutive chronology patches, build normalized pick vectors over the scenario roster. `shift_score` is Jensen-Shannon divergence between adjacent patch vectors.

## Turning points

A turning point is recorded at patch `patch_id` when the shift score from the immediately prior patch meets or exceeds `js_turn_threshold` from policy. Emit `shift_score` rounded to four decimal places.

## Patch note tags

`rationale_tag` for recommendations comes from the latest patch note (highest `seq`) whose headline contains the actor id case-insensitively. Map `stat_delta` to tags: negative `nerf_pressure`, positive `buff_pressure`, zero `tune_flat`. Headline keyword scans are not authoritative.

## Recommendations

Use the final era window. Rank actors by `diversity_deficit = pick_share * (1 - era_diversity)` descending (lexicographic actor id on ties). `priority` is 1-based rank order. Attach `rationale_tag` per actor from patch notes.

## Archive digest

`archive_digest` is exactly 16 lowercase hexadecimal characters: the first 16 hex digits of a SHA-256 (`sha256`) digest over UTF-8 segments sorted lexicographically and joined with newline (no trailing newline): scenario chronology file, matches file, notes file, and `policy/balance_policy.json`, each prefixed with its path relative to `/app/environment`.

## Output schema (`schema_version` 2)

| field | type | meaning |
|-------|------|---------|
| scenario | string | manifest name |
| eras | array | era rows with id, start_patch, end_patch, dominant_actor, diversity_index, dominant_win_lower |
| turning_points | array | patch_id and shift_score pairs |
| recommendations | array | actor, priority, rationale_tag |
| archive_digest | string | sixteen hex chars |

## CLI

`/opt/simbin/balancectl --scenario <name> --out /app/output/balance_archive.json`

Rebuild: `make -C /app/environment all`

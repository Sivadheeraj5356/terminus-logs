# ClaimTower local format contract

This repository contains an unfinished Go CLI at `/workspace/cmd/claimtower`. The milestone instruction files are the task prompts. This document is a visible local schema and business-rule reference for those prompts; it does not add hidden work beyond the milestone instructions.

## Common output and issue rules

All output files must create parent directories, use deterministic ordering, and end with exactly one newline. Every JSON output must be written as 2-space indented JSON with a final newline, equivalent to `json.MarshalIndent(value, "", "  ")` followed by `\n`.

Recoverable input problems must be reported to the requested issue TSV and must not stop processing of later valid records. Issue TSV files always use this header:

`source_file\tsource_line\tkind\tentity\tdetail`

Issue rows sort by `source_file`, numeric `source_line`, `kind`, `entity`, and `detail`. Source file values are absolute paths. For a whole-file or command-level attribution problem, use line `0`. For a non-object JSONL row, use an empty entity. For a JSONL row problem, use the 1-based line number in the source file.

The CLI must use only the Go standard library. Do not use network access, subprocesses, CGO, plugins, or third-party modules.

## Milestone 1: ingest

Command:

`go run /workspace/cmd/claimtower ingest --claims-root <dir> --as-of YYYY-MM-DD --claims-out <json> --issues-out <tsv>`

Read files ending in `.claim.jsonl` or `.claim.jsonl.gz` recursively. Each row is a JSON object. Field aliases are `claim_id`/`id`, `revision`/`rev`, `product`/`line`, `loss_date`/`lossOn`, and `status`/`state`. Required fields are claim id, revision, product, loss date, status, reserve, paid, and severity. Reserve and paid are non-negative integers. Severity is integer 1 through 5. Loss date must be `YYYY-MM-DD` and not after `--as-of`. Status is lower-cased. Closed, cancelled, and canceled claims are valid but ignored from the final claim list.

For duplicate valid open records with the same claim id, keep the highest revision. If revision ties, keep the row from the lexicographically smaller absolute source file, then the smaller source line.

The claim JSON output contains `as_of`, `claim_count`, `claims`, and `totals`. Claim objects contain `claim_id`, `product`, `loss_date`, `status`, `reserve`, `paid`, `severity`, `handler`, `county`, `revision`, `age_days`, `source_file`, and `source_line`; sort claims by `claim_id`. Totals contain `open_claims`, `reserve`, and `paid`.

Use issue kind `invalid_claim` for recoverable claim-row problems. The canonical `detail` tokens are:

| Problem | `detail` |
|---|---|
| malformed JSON text | `bad_json` |
| JSON value is not an object | `not_object` |
| missing, blank, or wrong-type claim id | `claim_id` |
| missing or wrong-type revision | `revision` |
| missing, blank, or wrong-type product | `product` |
| missing, wrong-type, or unparsable loss date | `loss_date` |
| loss date after `--as-of` | `loss_date_after_as_of` |
| missing or wrong-type status | `status` |
| missing, wrong-type, or negative reserve | `reserve` |
| missing, wrong-type, or negative paid | `paid` |
| missing, wrong-type, or out-of-range severity | `severity` |

For field-specific `invalid_claim` rows, set `entity` to the claim id when one is present; otherwise leave it empty.

## Milestone 2: score

Command:

`go run /workspace/cmd/claimtower score --claims-in <claims.json> --signals-root <dir> --rules <rules.tsv> --signals-out <tsv> --index-out <json> --issues-out <tsv>`

Read the milestone 1 claim JSON, a rules TSV, and signal files ending in `.signal.jsonl` or `.signal.jsonl.gz`. The rules TSV header is exactly `code\tbase_points\tage_days\tmultiplier\tlabel`. Rule numeric fields are integers. If the rules TSV header is malformed, emit the documented `invalid_signal`/`rules_header` issue for line 1, then continue scanning later data rows positionally as `code`, `base_points`, `age_days`, `multiplier`, and `label`; a later malformed data row must still produce the documented `rules_row` issue instead of being skipped just because the header was bad. Signal rows are JSON objects with claim id (`claim_id` or `id`), signal code (`signal_code` or `code`), revision (`revision` or `rev`), `observed_on`, `strength`, and optional `action`. Strength is integer 1 through 5. Action defaults to active; `retract` means the latest selected row removes that claim/code candidate. For each claim/code, select the highest revision, then lexicographically smaller absolute source file, then smaller source line.

Score each active selected signal as: `base_points + strength*2 + claim.severity*3 + reserve_gap_bonus + age_bonus`. `reserve_gap_bonus` is floor((reserve - paid) / 10000), never below zero. `age_bonus` is the rule multiplier when the claim age is at least the rule `age_days`, otherwise zero.

Write `signals_out` with header `claim_id\tsignal_code\tlabel\tscore\tstrength\tobserved_on\tclaim_severity\tage_days\tsource_file\tsource_line`. The `age_days` column is the claim's computed age from the milestone 1 claim JSON, not the rule threshold from `rules.tsv`. Sort rows by `claim_id`, descending score, then `signal_code`. The `source_file` and `source_line` columns must point to the selected signal row that produced the candidate.

Write `index_out` JSON with `as_of`, `claim_count`, `candidate_count`, and `claims`. `claim_count` is copied from the input claim report, even when some claims have no active scored signal. `candidate_count` is the number of rows written to `signals_out` excluding the header. Index claim objects contain `claim_id`, `product`, `county`, `severity`, `reserve`, `paid`, `age_days`, `total_score`, and `signals`; include only claims with at least one active scored signal in the `claims` array. Each nested object in `claims[].signals[]` uses JSON field names `code`, `label`, `score`, `strength`, and `observed_on`. Use `code` in the nested JSON signal objects even though the TSV column is named `signal_code`. Sort index claims by descending `total_score`, then `claim_id`. Sort each claim's signals by descending score, then `code`.

Signal and rule problems are recoverable. Use these canonical issue kinds and `detail` tokens:

| Problem | `kind` | `entity` | `detail` |
|---|---|---|---|
| malformed signal JSON text | `invalid_signal` | empty | `bad_json` |
| signal JSON value is not an object | `invalid_signal` | empty | `not_object` |
| missing, blank, or wrong-type claim id | `invalid_signal` | empty if unknown, else claim id | `claim_id` |
| missing, blank, or wrong-type signal code | `invalid_signal` | claim id if present | `signal_code` |
| missing or wrong-type revision | `invalid_signal` | claim id if present | `revision` |
| missing, wrong-type, or unparsable observed date | `invalid_signal` | claim id if present | `observed_on` |
| observed date after the claim report `as_of` | `invalid_signal` | claim id | `observed_on_after_as_of` |
| missing, wrong-type, or out-of-range strength | `invalid_signal` | claim id if present | `strength` |
| signal claim id absent from input claim JSON | `missing_claim` | missing claim id | signal code |
| signal code absent from rules TSV | `missing_rule` | claim id | missing signal code |
| rules TSV header is not exact | `invalid_signal` | empty | `rules_header` |
| rules TSV row has wrong column count, blank code, or bad numeric field | `invalid_signal` | rule code if present | `rules_row` |

## Milestone 3: assign

Command:

`go run /workspace/cmd/claimtower assign --index-in <index.json> --capacity <capacity.tsv> --plan <plan.json> --assignments-out <tsv> --summary-out <json> --issues-out <tsv>`

The command reads the Milestone 2 signal index, a recoverable capacity TSV, and a strict assignment-plan JSON. It must optimize claim selection, day placement, and team assignment jointly. A sequential or greedy assignment is not equivalent to the required result.

### Capacity roster

The capacity TSV header is exactly:

`team\tproducts\tcounties\tday1\tday2\trisk_ceiling\tactive`

`products` and `counties` are comma-separated lists or `*`. `day1`, `day2`, and `risk_ceiling` are non-negative integers. `active` accepts true/false, yes/no, or 1/0. A malformed header emits `invalid_capacity` with detail `header` at source line 1, but later rows are still parsed positionally as the fixed seven columns. Invalid data rows emit `invalid_capacity` with detail `row` and do not create a team.

### Strict assignment-plan JSON

The plan is one JSON object with exactly these required top-level fields. Unknown fields are fatal.

```json
{
  "max_total_score": 300,
  "team_day_score_limits": {
    "TeamA": {"day1": 180, "day2": 140}
  },
  "team_signal_skills": {
    "TeamA": ["FRAUD", "RESERVE"]
  },
  "claim_windows": {
    "CLM-1": ["day1"],
    "CLM-2": ["day1", "day2"]
  },
  "blocked_same_day": [["CLM-1", "CLM-3"]],
  "requires": [["CLM-4", "CLM-2"]],
  "precedence": [
    {"before": "CLM-2", "after": "CLM-5", "min_day_gap": 1}
  ],
  "same_team_groups": [["CLM-2", "CLM-5"]],
  "different_team_pairs": [["CLM-1", "CLM-4"]],
  "bundle_bonuses": [
    {"claims": ["CLM-2", "CLM-5"], "bonus": 40, "same_day": false}
  ]
}
```

Validation rules:

- `max_total_score` is a non-negative integer and limits the sum of `total_score` for all assigned claims.
- `team_day_score_limits` must contain every valid capacity team, active or inactive. Each entry contains non-negative integer `day1` and `day2` limits. Unknown team keys are fatal.
- `team_signal_skills` must contain every valid capacity team. Each list is nonempty, contains unique nonblank tokens, and may contain `*` as a wildcard. Unknown team keys are fatal.
- `claim_windows` may omit a claim, which means both days are allowed. A present claim must exist in the index and have a nonempty unique list containing only `day1` and/or `day2`.
- `blocked_same_day`, `requires`, and `different_team_pairs` contain two distinct existing claim ids per entry.
- A `precedence` entry references two distinct existing claims and uses `min_day_gap` 0 or 1.
- Each `same_team_groups` entry contains at least two distinct existing claims.
- Each `bundle_bonuses` entry contains at least two distinct existing claims, a non-negative integer bonus, and a boolean `same_day`.
- Missing required fields, unknown fields, unknown references, duplicate members inside a group or bonus, invalid days, or invalid numeric values are fatal. Fatal plan errors must return nonzero before creating or replacing assignments, summary, or issue outputs.

### Eligibility and feasible schedule choices

The claim lane remains `expedited` for score at least 80, `standard` for score at least 50, and `monitor` otherwise.

A team is statically eligible for a claim when all of these are true:

1. the team row is active;
2. product and county match the capacity row, including `*` wildcards;
3. claim `total_score` is at most the team's `risk_ceiling`;
4. the team's skill list contains `*` or the claim's primary signal code.

The primary signal is the first object in the index claim's `signals` array. Milestone 2 already orders that array by descending signal score and then code.

A claim with no statically eligible team becomes `hold_no_team`. This decision ignores slot counts, team/day score budgets, and relationship constraints. Emit the same `no_team` issue used by v12: source file is the absolute capacity path, source line 0, entity is the claim id, and detail is `product/county`.

For a statically eligible claim, a concrete `(team, day)` choice is available only when:

- the day is allowed by the claim window;
- the capacity row has at least one slot for that day;
- the claim score does not exceed that team's plan score limit for that day.

A statically eligible claim that is not assigned in the winning portfolio uses `backlog_capacity`, even when the reason is a global budget, relationship, day window, or team/day limit.

### Portfolio constraints

A feasible schedule must satisfy all of these rules:

- Assigned raw score must not exceed `max_total_score`.
- For every team/day, assigned claim count must not exceed the capacity TSV slot count.
- For every team/day, assigned raw score must not exceed `team_day_score_limits`.
- `blocked_same_day`: when both claims are assigned, they must be on different days.
- `requires`: each pair is `[dependent, prerequisite]`; assigning the dependent requires assigning the prerequisite, with no implied day or team relationship.
- `precedence`: assigning `after` requires assigning `before`, and `day(after) - day(before)` must be at least `min_day_gap`, where day1 is 1 and day2 is 2.
- `same_team_groups`: all assigned members of the group must use one team. Unassigned members do not force the rest of the group to be selected.
- `different_team_pairs`: when both claims are assigned, their teams must differ.
- A bundle bonus is earned only when every listed claim is assigned. When `same_day` is true, all listed claims must also share one day. Bundle bonuses do not consume score budgets.

### Objective and deterministic tie-break

For every feasible schedule calculate:

- `total_score_used`: sum of assigned claim `total_score` values;
- `bonus_value`: sum of all earned bundle bonuses;
- `plan_value = total_score_used + bonus_value`.

Choose the winning schedule by this exact priority order:

1. larger `plan_value`;
2. larger assigned claim count;
3. smaller `total_score_used`;
4. lexicographically smaller schedule key.

Build the schedule key by sorting assigned claim ids lexicographically and joining entries of the form `claim_id:day:team` with `|`. Unassigned claims are not included. For example:

`CLM-A:day1:Alpha|CLM-C:day2:Beta`

This tie-break applies to the complete portfolio, not one claim at a time.

### Outputs

The assignment TSV header remains:

`claim_id\tlane\tstatus\tteam\tday\ttotal_score\tproduct\tcounty\tsignal_count`

Rows remain in processing order: expedited, standard, monitor; descending total score inside each lane; then claim id. Assigned rows contain the winning team and day. Backlog and hold rows leave team and day empty.

The summary JSON contains exactly these top-level fields:

- `assigned_count`
- `backlog_count`
- `hold_count`
- `plan_value`
- `bonus_value`
- `total_score_used`
- `lanes`
- `days`
- `teams`

`lanes` counts every processed index claim by lane, regardless of status.

`days` is always an array in this order: day1, day2. Each object contains `day`, `assigned_count`, and `score_used`.

`teams` is sorted by team name and contains every valid capacity team, including inactive teams. Each team object contains:

- `team`
- `day1_used`
- `day2_used`
- `day1_score_used`
- `day2_score_used`
- `remaining_day1`
- `remaining_day2`
- `remaining_day1_score`
- `remaining_day2_score`
- `assigned_claims`

Remaining slot values are capacity slots minus assigned counts. Remaining score values are plan score limits minus assigned raw score. `assigned_claims` is sorted by claim id and must be `[]`, not `null`, when empty.

Assignment issues use these canonical rows:

| Problem | `kind` | `source_file` | `source_line` | `entity` | `detail` |
|---|---|---|---|---|---|
| capacity TSV header is not exact | `invalid_capacity` | absolute capacity TSV path | `1` | empty | `header` |
| capacity row has wrong column count, blank team, bad integer, negative integer, or bad active value | `invalid_capacity` | absolute capacity TSV path | source row number | team value if present | `row` |
| no active statically eligible team exists for a claim | `no_team` | absolute capacity TSV path | `0` | claim id | `product/county` such as `liability/south` |


# Analyze `/app/xwing-data/input/candidate_layouts.tsv` and deliver three data pro

Submission: `1dd3732a-b566-417d-9608-a153866b53eb`  
Slug: `analyze-app-xwing-data-input-candidate-layouts-tsv-and-deliv`  
Latest archive: `1dd3732a-b566-417d-9608-a153866b53eb_submission_2026-07-15T21_05_51.948Z.zip`  
Revisions: 5

## Task summary

Analyze `/app/xwing-data/input/candidate_layouts.tsv` and deliver three data products: `/app/out/fish_targets.tsv`, `/app/out/fish_ratings.tsv`, and `/app/out/fish_summary.json`. The input has `name` and `candidate_spec`; a spec uses semicolon-separated `digit:cells` groups and comma-separated `r1c1` cells, with repeats treated as set entries. The target ledger header is `name\tdigit\ttarget\tsize\tfamily\tfin_state\tbase_houses\tcover_houses\texo_fins\tendo_fins\tcannibalistic`. Emit one row per selected target, ordered by name, digit, row, and column. Houses and fin cells are lexical comma-sorted lists, empty fin lists use `-`, and `cannibalistic` is `true` or `false`. The ratings header is `name\ttier\tsizes\tfamilies\tfin_states\tfish_digits\tendo_fin_digits\tcannibalistic_digits\telimination_targets`; emit one name-sorted row per input, lexical comma-sorted lists, `-` for empty lists, and numeric target ordering. For each digit, census productive fish of sizes 2 through 4 over houses `R1`-`R9`, `C1`-`C9`, and `B1`-`B9`. Select equal numbers of distinct base and cover houses without reusing a house; every base must contain at least two source candidates. Base candidates occur in a selected base. Exo fins occur in no cover, endo fins occur in multiple bases, and core candidates occur in exactly one base and at least one cover; every selected house needs a core candidate. Possible targets are non-base candidates in a cover plus non-fin base candidates in multiple covers. When fins exist, a target must share a row, column, or box with every fin. Sizes are `X_WING`,...

Required artifacts include: `/app/xwing-data/input/candidate_layouts.tsv`, `/app/out/fish_targets.tsv`, `/app/out/fish_ratings.tsv`, `/app/out/fish_summary.json`.

Author anonymous tagged this **hard** data-processing task (tabular-data, data-analysis, reporting, aggregation, sudoku).

Time estimates: expert ~150 min, junior ~300 min.

Harbor timeouts: agent 600.0s, verifier 300.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `1dd3732a-b566-417d-9608-a153866b53eb_submission_2026-07-15T21_05_51.948Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`

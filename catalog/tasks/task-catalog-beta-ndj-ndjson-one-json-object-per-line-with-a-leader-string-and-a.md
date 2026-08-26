# ## Task

Submission: `49505eba-bfe8-463e-8a1d-6e690a89810a`  
Slug: `task-catalog-beta-ndj-ndjson-one-json-object-per-line-with-a-leader-string-and-a`  
Latest archive: `49505eba-bfe8-463e-8a1d-6e690a89810a_submission_2026-07-06T06_48_14.829Z.zip`  
Revisions: 2

## Task summary

catalog_beta.ndj (NDJSON): one JSON object per line with a leader string and a fields array. A field is either control (tag plus value) or data (tag, ind1, ind2, subfields array of code and value). catalog_gamma.fwt (fixed width): leader lines are `LEADER:` followed by the 24 char leader. Field lines are `TAG=nnn LEN=llll OFFS=ooooo DATA=body` where body is two indicators plus dollar subfields for data tags. `ENDREC` ends the record.

Required artifacts include: `/app/shelves`, `/app/output/report.json`, `/app/catalog/report_shape.json`, `/app/seals`, `/app/bin/marcrec`.

Author anonymous tagged this **hard** data-processing task (marc21, bibliographic-records, multi-format, hmac-pin, cascade-arming).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `49505eba-bfe8-463e-8a1d-6e690a89810a_submission_2026-07-06T06_48_14.829Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`

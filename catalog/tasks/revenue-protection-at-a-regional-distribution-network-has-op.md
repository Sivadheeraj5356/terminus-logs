# Revenue protection at a regional distribution network has opened a meter-fraud c

Submission: `3c219701-ea00-430f-8254-e5e0dbed8b93`  
Slug: `revenue-protection-at-a-regional-distribution-network-has-op`  
Latest archive: `3c219701-ea00-430f-8254-e5e0dbed8b93_submission_2026-07-19T04_03_30.445Z.zip`  
Revisions in Dropbox: 5

## Task summary

Revenue protection at a regional distribution network has opened a meter-fraud case, and our firm has the forensic audit. Field crews keep pulling tapped service heads off circuits whose exports look clean, the same meter credential keeps turning up at delivery points minutes apart, and a run of settlement disputes has been quietly writing off charges that should have stood. The seized evidence sits in a corpus shaped like /app/data: the network registry, the utilities' raw binary meter exports under exports/, the regulator's circular book under circulars/, and the disputes file. The board wants a case report it can reproduce on any corpus, and a review service the tribunal can read the closed case through. The format sheet /app/spec/FORMATS.md lists every layout and schema (the corpus paths, the registry field table, the packed record layout with an annotated hex dump, the circular grammar, the schema of every report file, the two database table schemas, and the HTTP response shapes), and /app/spec/RULES.md carries the complete rule set for all five subcommands. The directory /app/data/example holds a small worked corpus to exercise the engine on before the dense one; grading is byte-exact on unseen corpora. Mechanize the audit as a single Rust program under /app/tariff whose binary is named tariff, built with make -C /app/tariff build and producing /app/tariff/target/release/tariff. The one binary carries five subcommands that build on each other: tariff intake --data DIR --out DIR parses the meter exports and logs the evidence; tariff draws --data DIR --out DIR...

Required artifacts include: `/app/data`, `/app/spec/FORMATS.md`, `/app/spec/RULES.md`, `/app/data/example`, `/app/tariff`, `/app/tariff/target/release/tariff`.

Author anonymous tagged this **hard** security task (meter-fraud, revenue-assurance, forensics, evidence-integrity, fraud-detection, progressive-tariff).

Time estimates: expert ~210 min, junior ~480 min.

Harbor timeouts: agent 1800.0s, verifier 1800.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `3c219701-ea00-430f-8254-e5e0dbed8b93_submission_2026-07-19T04_03_30.445Z.zip` is a task submission, not a Harbor job. 5 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`

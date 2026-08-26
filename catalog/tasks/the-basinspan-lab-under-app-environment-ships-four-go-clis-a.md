# The BasinSpan lab under /app/environment ships four Go CLIs and a Rust merge ker

Submission: `607bed84-a099-419c-9c59-328be106f2dc`  
Slug: `the-basinspan-lab-under-app-environment-ships-four-go-clis-a`  
Latest archive: `607bed84-a099-419c-9c59-328be106f2dc_submission_2026-07-18T08_01_53.867Z.zip`  
Revisions: 1

## Task summary

The BasinSpan lab under /app/environment ships four Go CLIs and a Rust merge kernel for neuron-aligned feedforward weight merging. The tree builds and runs, but campaign output still disagrees with /app/environment/docs/basinspan_contract.txt. Fix the Go and Rust sources under /app/environment to match that contract, then rebuild with /app/environment/scripts/rebuild.sh (see /app/environment/docs/toolchain.md). Hand-written or static output under /app/output is insufficient; the normal pipeline must regenerate every artifact. After rebuild you should have basinspan-run, basinspan-probe, basinspan-audit, and basinspan-inspect in /app/environment/build/. basinspan-run reads the manifest and policy, evaluates each pair profile, and writes merge_report.json, alignment_trace.csv, merge_journal.jsonl, and barrier_certificate.json under /app/output, plus align_cache.json and merge_ledger.json under /app/var/basinspan. Use --reset to clear persisted state before a campaign; without --reset each run increments generation and ledger counters as the contract describes. BASINSPAN_MANIFEST, BASINSPAN_PAIR_DIR, and BASINSPAN_POLICY_EPOCH override the manifest path, pair directory, and policy epoch.

Required artifacts include: `/app/environment`, `/app/environment/docs/basinspan_contract.txt`, `/app/environment/scripts/rebuild.sh`, `/app/environment/docs/toolchain.md`, `/app/output`, `/app/environment/build/`, `/app/var/basinspan`.

Author anonymous tagged this **hard** machine-learning task (model-merging, hungarian, weight-alignment, neuron-permutation, feedforward).

Time estimates: expert ~120 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `607bed84-a099-419c-9c59-328be106f2dc_submission_2026-07-18T08_01_53.867Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`

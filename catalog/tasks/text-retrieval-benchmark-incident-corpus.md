# # Text Retrieval Benchmark: Incident Corpus

Submission: `ca236e14-453a-42d7-904c-cc026802e84f`  
Slug: `text-retrieval-benchmark-incident-corpus`  
Latest archive: `ca236e14-453a-42d7-904c-cc026802e84f_submission_2026-07-11T02_58_32.410Z.zip`  
Revisions: 4

## Task summary

The corpus at `/app/data/incident_transcript.txt` is a multi-day production incident transcript. Build a natural-language retrieval index over this corpus, evaluate its ranking quality against held-out queries, and expose the retrieval and evaluation interfaces so they can be graded. For a natural-language question, produce a ranked list of the top-k passages and a short synthesised answer:

Required artifacts include: `/app/data/incident_transcript.txt`, `/app/static/`.

Author anonymous tagged this **hard** machine-learning task (rag, nlp, information-retrieval, text-retrieval, bm25, tf-idf, ranking).

Time estimates: expert ~90 min, junior ~180 min.

Harbor timeouts: agent 1200.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `ca236e14-453a-42d7-904c-cc026802e84f_submission_2026-07-11T02_58_32.410Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`

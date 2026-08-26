# Model risk review keeps an offline pharmacy conformal-prediction evaluator under

Submission: `4ad8d490-d181-41b3-85d8-c387b4e282b6`  
Slug: `model-risk-review-keeps-an-offline-pharmacy-conformal-predic`  
Latest archive: `4ad8d490-d181-41b3-85d8-c387b4e282b6_submission_2026-07-20T12_15_23.961Z.zip`  
Revisions in Dropbox: 1

## Task summary

Model risk review keeps an offline pharmacy conformal-prediction evaluator under `/app/environment`. The evaluator scores pharmacy-ops uncertainty briefs under frozen conformal calibration annexes and must keep coverage behavior stable on held-out cross-border board pairs (adversarial generalization / out-of-distribution pairs). Repair the sources under `/app/environment` so the evaluator can read the jurisdiction corpus, frozen conformal calibration runs under `/app/environment/data/cal/`, and the long-context board shards under `/app/environment/data/long_ctx/`, then write `/app/output/readiness_gonogo_brief.json`. That JSON must include gate_rows, rb_rows, seg_trace, and a 64-character lowercase hex brief_digest; each gate row carries clause_ids, seg_vec, disc_bind, and gate_kind; each rollback row carries metric_fam, bind_stamp, and hx_ref. Packing formulas and conformal scoring flags live in `/app/environment/docs/seal_k4.md`. The closed training pack under `/app/environment/data/pack_tr` rebuilds a brief that looks coherent on layout checks today, but cross-border held-out pair packs under `/app/environment/data/xp/` still fail desk obligation checks. Uncertainty disclosure language from one state board wins where another board's rules should govern, conformal segment totals in the brief disagree with the calibration annex after refresh stamps advance, and rollback rows latch onto the wrong metric family after a rerun.

Required artifacts include: `/app/environment`, `/app/environment/data/cal/`, `/app/environment/data/long_ctx/`, `/app/output/readiness_gonogo_brief.json`, `/app/environment/docs/seal_k4.md`, `/app/environment/data/pack_tr`, `/app/environment/data/xp/`, `/app/environment/scripts/run_k4.sh`.

Author anonymous tagged this **hard** machine-learning task (machine-learning, conformal, calibration, long-context, ood, pharmacy).

Time estimates: expert ~150 min, junior ~360 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `4ad8d490-d181-41b3-85d8-c387b4e282b6_submission_2026-07-20T12_15_23.961Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`

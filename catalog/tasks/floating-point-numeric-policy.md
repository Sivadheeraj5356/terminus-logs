# floating_point_numeric_policy

Submission: `5d7231b2-e692-4b71-800b-eded87c740c0`  
Slug: `floating-point-numeric-policy`  
Latest archive: `5d7231b2-e692-4b71-800b-eded87c740c0_submission_2026-07-18T13_14_22.705Z.zip`  
Revisions: 1

## Task summary

A seeded machine-learning training harness under `/app/environment` (Node) runs optimizer update loops with first/second moment accumulators and a learning-rate schedule over local fixture data, and supports halt-and-continue training. Resumed training must reproduce the same learning curves as an uninterrupted training run over the same inputs. After a halt-and-continue cycle, `/app/output/stage` headline totals and `/app/environment/fixtures/interim/q3_hold.json` can look acceptable while the graded training audit still shows the resumed curve disagreeing with the uninterrupted curve for the same inputs. Update the training implementation under `/app/environment` so that a normal regeneration of the training audit outputs satisfies the public contracts. Driver-only tweaks, hand-editing `/app/output`, or static/manual JSON writes are not enough; the verifier rebuilds and reruns the training pipeline from source.

Required artifacts include: `/app/environment`, `/app/output/stage`, `/app/environment/fixtures/interim/q3_hold.json`, `/app/output`, `/app/environment/guide/pol_table.md`, `/app/environment/guide/out_shape.md`, `/app/environment/guide/id_list.txt`, `/app/environment/fixtures/frames/`.

Author anonymous tagged this **hard** machine-learning task (machine-learning, training, javascript, checkpoint, optimizer, floating-point).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `5d7231b2-e692-4b71-800b-eded87c740c0_submission_2026-07-18T13_14_22.705Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`

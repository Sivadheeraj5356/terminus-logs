# This is a supervised machine-learning task: learn a labeling rule from labeled e

Submission: `7526fd70-f095-4fa8-bbd8-a555033c4780`  
Slug: `this-is-a-supervised-machine-learning-task-learn-a-labeling-`  
Latest archive: `7526fd70-f095-4fa8-bbd8-a555033c4780_submission_2026-07-18T08_33_17.646Z.zip`  
Revisions in Dropbox: 1

## Task summary

This is a supervised machine-learning task: learn a labeling rule from labeled examples and predict labels for new examples. Each instance is a directory with two files. train.csv holds labeled training examples, one row each of four small integer features f0, f1, f2, f3 with a 0 or 1 label. test.csv holds unlabeled examples with the same four features. A single hidden rule, fixed within the instance, generated every training label, and the same rule labels the test examples. The task is to learn that rule from the training examples and predict the label of each test example. The examples form an ordered sequence, and the rule the model must learn depends on the current example's features together with a bounded amount of information carried from earlier examples, so a model that treats the examples as independent will not fit the labels; not every feature necessarily matters. The carried information is small and integer-valued — think of a single running counter that accumulates along the sequence and resets to zero at a hidden bound — and the parameters that govern the rule lie in a modest range. Each instance has its own hidden parameters, so the rule is learned from each instance's own training examples rather than memorized once. The training labels let a learned model check itself on the training examples, while the graded instances are held out with new examples and new parameters; scoring is by prediction accuracy on the hidden labels, so a model that fits the training examples without recovering the underlying rule generalizes poorly and scores poorly.

Required artifacts include: `/app/environment`, `/app/environment/target/release/solver`, `/app/environment/data`, `/app/environment/docs/contract.md`.

Author anonymous tagged this **hard** machine-learning task (supervised-learning, sequence-labeling, rule-induction, stateful-rule, self-resetting-accumulator, delayed-threshold).

Time estimates: expert ~420 min, junior ~720 min.

Harbor timeouts: agent 1800s, verifier 300s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `7526fd70-f095-4fa8-bbd8-a555033c4780_submission_2026-07-18T08_33_17.646Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Model or pipeline trains/runs but misses accuracy, format, or artifact-path gates.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`

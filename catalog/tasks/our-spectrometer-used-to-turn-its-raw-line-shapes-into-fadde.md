# Our spectrometer used to turn its raw line shapes into Faddeeva-function values,

Submission: `873e2378-744d-4e8d-a642-abdc884bcc28`  
Slug: `our-spectrometer-used-to-turn-its-raw-line-shapes-into-fadde`  
Latest archive: `873e2378-744d-4e8d-a642-abdc884bcc28_submission_2026-07-19T06_40_01.188Z.zip`  
Revisions: 1

## Task summary

Our spectrometer used to turn its raw line shapes into Faddeeva-function values, and the little evaluator that did it got lost in a disk wipe. I need it rebuilt, and the replacement has to cover more ground than the old one did. The optics group now probes the gain region below the real axis too, where the function blows up so fast that its raw parts overflow any float, so the engine reports each value as the natural log of its modulus together with its phase. Write /app/faddeeva.js so that `node /app/faddeeva.js <path-to-batch>` reads a JSON Lines batch of complex arguments and prints, one line per request in input order, the log-modulus and the phase of w(z). The exact value definition, the request format, the argument ranges, the output format, and the accuracy each number has to hit are in /app/spec.md, and there is a sample batch at /app/requests.jsonl you can run it on. Node standard library only, the box is offline, and it will be run on other batches from the same ranges, some of them large, so it has to stay accurate across the whole range and not crawl on big inputs. Fair warning from the last person who tried: at the biggest arguments the accuracy bar sits below what plain double arithmetic can carry, so the arithmetic itself needs real thought, not just the right formula.

Required artifacts include: `/app/faddeeva.js`, `/app/spec.md`, `/app/requests.jsonl`.

Author anonymous tagged this **hard** scientific-computing task (numerical-methods, special-functions, faddeeva, voigt-profile, nodejs).

Time estimates: expert ~240 min, junior ~600 min.

Harbor timeouts: agent 1800.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `873e2378-744d-4e8d-a642-abdc884bcc28_submission_2026-07-19T06_40_01.188Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Numeric or scientific result is plausible but fails exact/held-out checks.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`

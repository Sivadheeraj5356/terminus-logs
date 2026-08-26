# # Poset Chomp: game value, Grundy value, and remoteness

Submission: `88f91d1f-9208-42aa-9df6-3fb94b729603`  
Slug: `poset-chomp-game-value-grundy-value-and-remoteness`  
Latest archive: `88f91d1f-9208-42aa-9df6-3fb94b729603_submission_2026-07-18T02_51_49.874Z.zip`  
Revisions: 1

## Task summary

Chomp is played on the order ideals of a finite partially ordered set (poset). For one position you must report four exact quantities under the **normal poison-loss** convention: the game value, the number of winning first moves, the Sprague-Grundy value, and the remoteness (optimal game length). Complete the C++ program in `src/` so that `make` builds `./chomp`; it reads one position from stdin and writes a single line `V C G R` to stdout. Elements are labelled `0 .. n-1`. The order is the reflexive-transitive closure of the given **cover** relations: a pair `a b` means `a < b` is a covering relation (`a` immediately below `b`). Element `0` is the **poison**; it is the unique minimal element, so `0 < x` for every other element `x`.

Required artifacts include: not named as `/app` paths.

Author anonymous tagged this **hard** games task (chomp, combinatorial-game, poset-ideal, sprague-grundy, remoteness).

Time estimates: expert ~180 min, junior ~600 min.

Harbor timeouts: agent 1200s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=weak, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `88f91d1f-9208-42aa-9df6-3fb94b729603_submission_2026-07-18T02_51_49.874Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`

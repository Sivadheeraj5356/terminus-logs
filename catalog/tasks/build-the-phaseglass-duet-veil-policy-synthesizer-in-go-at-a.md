# Build the Phaseglass Duet veil-policy synthesizer in Go at "/app/cmd/phaseglass-

Submission: `d1b587ab-0515-4c32-8e9a-e9909637dab5`  
Slug: `build-the-phaseglass-duet-veil-policy-synthesizer-in-go-at-a`  
Latest archive: `d1b587ab-0515-4c32-8e9a-e9909637dab5_submission_2026-07-14T21_07_13.401Z.zip`  
Revisions: 4

## Task summary

Build the Phaseglass Duet veil-policy synthesizer in Go at "/app/cmd/phaseglass-duet". It must build with the provided Go toolchain and run as "go run /app/cmd/phaseglass-duet --board /app/boards/public.json --output /app/out/phaseglass_policy.json". A board contains several possible hidden world states, and the program never learns the hidden state directly. At each nonterminal policy node it chooses one simultaneous Amber/Cobalt action pair, observes movement results and beacon signals, and then the environment may adversarially choose any successor allowed by the joint tone. The observation is produced before that hidden transition, so one observation can lead to an expanded belief containing several successors. The chosen action pair must be legal and must avoid collisions, direct swaps, and tether violations for every hidden state in the current belief. A policy succeeds only when every possible run reaches both goal rooms in accepting hidden states within "max_turns"; reaching the rooms while any possible hidden state is non-accepting is not terminal. Find the exact best strong policy, comparing candidates by lower worst terminal turn, lower worst boost count, lower worst energy, lower sum of each initial world's worst terminal turn across all allowed drift choices, and finally the lexicographically smaller complete recursive policy using the action and observation orders in the rules file. Output a canonical breadth-first policy DAG: assign IDs "N0", "N1", and so on by visiting branches in bytewise observation order, and reuse one node whenever tick, positions,...

Required artifacts include: `/app/cmd/phaseglass-duet`, `/app/boards/public.json`, `/app/out/phaseglass_policy.json`, `/app/docs/phaseglass_veil_rules.txt`.

Author anonymous tagged this **hard** games task (games, partial-observation, policy-synthesis, belief-state-search, adversarial-planning).

Time estimates: expert ~90 min, junior ~180 min.

Harbor timeouts: agent 1800.0s, verifier 900.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `d1b587ab-0515-4c32-8e9a-e9909637dab5_submission_2026-07-14T21_07_13.401Z.zip` is a task submission, not a Harbor job. 4 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Game/engine behavior is mostly right but fails a replay, score, or state-hash test.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`

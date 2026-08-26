# Each challenge in a batch fixes a modulus `n` and publishes a list of rows, each

Submission: `43df573d-66ad-483c-95df-96bc527959ce`  
Slug: `each-challenge-in-a-batch-fixes-a-modulus-n-and-publishes-a-`  
Latest archive: `43df573d-66ad-483c-95df-96bc527959ce_submission_2026-07-17T15_14_11.427Z.zip`  
Revisions in Dropbox: 1

## Task summary

Each challenge in a batch fixes a modulus `n` and publishes a list of rows, each row a triple `(e, f, c)`. Behind every challenge sit two secret integers, a message `m` and a mask base `s`, and a row that is authentic satisfies `c = m^e * s^f (mod n)`. Not every published row is guaranteed to be authentic, the published values are not guaranteed to be written in canonical form, and neither `s`, nor the factorization of `n`, nor which rows are authentic is ever given; there is no decryption oracle. The message of a challenge is exactly `L` bytes big-endian, `L` is published with the challenge, and the first two bytes of that encoding are always `0xCA 0xFE`; the authentic rows together with that fixed header pin down `m` uniquely. The row count, the exponents, the arithmetic structure those exponents carry, and the modulus size all change from challenge to challenge and are redrawn for the graded batch. Recover the exact `m` for every challenge. Implement your solution in `/app/environment/attack/main.jl` (Julia, standard library only -- no packages are available or needed, and `Base`'s big-integer arithmetic is enough). It reads an input file and writes an output file exactly as `/app/environment/docs/io_contract.md` specifies. `/app/environment/samples/practice_challenges.txt` holds practice challenges in the graded input format. No answers ship with them, nothing on this host tells you which rows of a challenge are authentic, and no ground truth of any kind is available to you. `python3 /app/environment/samples/local_check.py julia /app/environment/attack/main.jl`...

Required artifacts include: `/app/environment/attack/main.jl`, `/app/environment/docs/io_contract.md`, `/app/environment/samples/practice_challenges.txt`, `/app/environment/samples/local_check.py`.

Author anonymous tagged this **hard** security task (rsa, number-theory, modular-arithmetic, cryptanalysis, plaintext-recovery).

Time estimates: expert ~270 min, junior ~600 min.

Harbor timeouts: agent 1800s, verifier 1800s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `43df573d-66ad-483c-95df-96bc527959ce_submission_2026-07-17T15_14_11.427Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`

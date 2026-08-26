# `/app` holds `mangle`, the candidate-generation stage of an offline password-cra

Submission: `0dc613a8-dab5-4767-b37b-64e7d806c854`  
Slug: `app-holds-mangle-the-candidate-generation-stage-of-an-offlin`  
Latest archive: `0dc613a8-dab5-4767-b37b-64e7d806c854_submission_2026-07-19T06_26_38.584Z.zip`  
Revisions: 3

## Task summary

`/app` holds `mangle`, the candidate-generation stage of an offline password-cracking pipeline used for credential-strength auditing. A rule-based dictionary attack takes a wordlist of leaked or guessed base words and a set of mangling rules (the transformations attackers apply to turn `summer` into `Summer2020!`, `$ummer`, `SUMMER`, and so on) and enumerates the guesses those rules produce. Reproducing this stage exactly matters: an auditor has to generate the same guess set a real attacker's toolchain would, so that "this password survives the attack" is a sound conclusion and not an artefact of a rule the auditor implemented differently. Build it with `make` in `/app` (equivalently `cc -O2 -std=c11 -o mangle src/main.c src/wordio.c src/rules.c`) and run `mangle <rulefile> <wordlist>`: for every base word, in file order, each rule is applied in file order and every surviving guess is written to standard output followed by a newline. Some rules **reject** a word, which is how an attack prunes its own keyspace, and a rejected pair, like a malformed rule, produces no guess. The rule interpreter in `/app/src/rules.c` is only a skeleton; the argument handling, file readers and driver loop in `/app/src/main.c` and `/app/src/wordio.c` already work. Implement `apply_rule` so it reproduces the mangling-rule language defined in `/app/docs/rules.md`, which is authoritative and self-contained: the case, edit, insertion, extraction, replacement, duplication, swap, byte-arithmetic and per-word memory functions that shape a guess, together with the reject functions that drop a word...

Required artifacts include: `/app/src/rules.c`, `/app/src/main.c`, `/app/src/wordio.c`, `/app/docs/rules.md`.

Author anonymous tagged this **medium** security task (password-cracking, wordlist, rule-engine, string-mangling, conformance).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `0dc613a8-dab5-4767-b37b-64e7d806c854_submission_2026-07-19T06_26_38.584Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`

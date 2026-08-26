# `/app` holds `mangle`, the candidate-generation stage of an offline password-cra

- **UUID:** `0dc613a8-dab5-4767-b37b-64e7d806c854`
- **Slug:** `app-holds-mangle-the-candidate-generation-stage-of-an-offlin`
- **Category:** security
- **Difficulty:** medium

## Summary

`/app` holds `mangle`, the candidate-generation stage of an offline password-cracking pipeline used for credential-strength auditing. A rule-based dictionary attack takes a wordlist of leaked or guessed base words and a set of mangling rules (the transformations attackers apply to turn `summer` into `Summer2020!`, `$ummer`, `SUMMER`, and so on) and enumerates the guesses those rules produce.

Reproducing this stage exactly matters: an auditor has to generate the same guess set a real attacker's toolchain would, so that "this password survives the attack" is a sound conclusion and not an artefact of a rule the auditor implemented differently. Build it with `make` in `/app` (equivalently `cc -O2 -std=c11 -o mangle src/main.c src/wordio.c src/rules.c`) and run `mangle <rulefile> <wordlist>`: for every base word, in file order, each rule is applied in file order and every surviving guess is written to standard output followed by a newline.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier

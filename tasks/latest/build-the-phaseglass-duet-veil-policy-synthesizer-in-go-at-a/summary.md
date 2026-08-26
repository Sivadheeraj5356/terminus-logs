# Build the Phaseglass Duet veil-policy synthesizer in Go at "/app/cmd/phaseglass-

- **UUID:** `d1b587ab-0515-4c32-8e9a-e9909637dab5`
- **Slug:** `build-the-phaseglass-duet-veil-policy-synthesizer-in-go-at-a`
- **Category:** games
- **Difficulty:** hard

## Summary

Build the Phaseglass Duet veil-policy synthesizer in Go at "/app/cmd/phaseglass-duet". It must build with the provided Go toolchain and run as "go run /app/cmd/phaseglass-duet --board /app/boards/public.json --output /app/out/phaseglass_policy.json".

A board contains several possible hidden world states, and the program never learns the hidden state directly. At each nonterminal policy node it chooses one simultaneous Amber/Cobalt action pair, observes movement results and beacon signals, and then the environment may adversarially choose any successor allowed by the joint tone.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier

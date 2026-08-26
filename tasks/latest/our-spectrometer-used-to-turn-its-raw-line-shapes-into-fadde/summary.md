# Our spectrometer used to turn its raw line shapes into Faddeeva-function values,

- **UUID:** `873e2378-744d-4e8d-a642-abdc884bcc28`
- **Slug:** `our-spectrometer-used-to-turn-its-raw-line-shapes-into-fadde`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Our spectrometer used to turn its raw line shapes into Faddeeva-function values, and the little evaluator that did it got lost in a disk wipe. I need it rebuilt, and the replacement has to cover more ground than the old one did.

The optics group now probes the gain region below the real axis too, where the function blows up so fast that its raw parts overflow any float, so the engine reports each value as the natural log of its modulus together with its phase. Write /app/faddeeva.js so that `node /app/faddeeva.js <path-to-batch>` reads a JSON Lines batch of complex arguments and prints, one line per request in input order, the log-modulus and the phase of w(z).

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier

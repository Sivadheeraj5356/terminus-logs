# Forty protection zones on the buried main (`zn-01` through `zn-40`, under /app/e

- **UUID:** `594e5dd1-5ed1-4741-8555-7c45aafa7439`
- **Slug:** `forty-protection-zones-on-the-buried-main-zn-01-through-zn-4`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Forty protection zones on the buried main (`zn-01` through `zn-40`, under /app/environment/data) are due for fresh sacrificial anodes before the coating survey closes. For each zone you decide a count of anodes to string on it, and you decide how that count divides between the cheap rationed stock and the pricier expediter.

Protection on a zone lasts as long as one of its anodes is still passing current at the end of the design life. Anodes corrode away on their own, one no faster for another failing beside it, so a zone strung with `n` anodes comes through the design life with probability `1 - (1 - p)^n`, in which `p` is that zone's own per-anode chance of lasting.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier

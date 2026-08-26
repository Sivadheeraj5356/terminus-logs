# Repair the Haskell tool in `/opt/cnfprep` so `make -C /opt/cnfprep` builds `/opt

- **UUID:** `9bf34249-7c49-45f6-8836-dbef31fe327c`
- **Slug:** `repair-the-haskell-tool-in-opt-cnfprep-so-make-c-opt-cnfprep`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Repair the Haskell tool in `/opt/cnfprep` so `make -C /opt/cnfprep` builds `/opt/cnfprep/bin/cnfprep` and the executable preprocesses DIMACS CNF files correctly. In normal mode it runs as `/opt/cnfprep/bin/cnfprep INPUT --out OUT --log LOG --map MAP`.

It must write a DIMACS CNF that is equisatisfiable with the input, has no duplicate literals, tautological clauses, unit clauses, pure literals, subsumed clauses, or applicable bounded variable eliminations left, and has a header that matches the emitted clauses. The audit log is line based.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier

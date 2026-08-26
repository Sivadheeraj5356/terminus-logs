# Build a MiniZinc model at /app/model.mzn that selects one valid rotamer at every

- **UUID:** `d095b2e9-56c2-4fb5-8fca-f851e26df0c4`
- **Slug:** `build-a-minizinc-model-at-app-model-mzn-that-selects-one-val`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Build a MiniZinc model at /app/model.mzn that selects one valid rotamer at every protein residue and a compatible set of disulfide bridges. The design must satisfy composition, charge, mutation, clash, bridge-matching, and multistate stability requirements while minimizing the specified robust energy objective.

The complete mathematical contract is in /app/contract.md, all input declarations are in /app/data_schema.mzn, and /app/output_contract.md defines the required JSON certificate. Solve /app/instance.dzn and keep all dimensions parameterized for same-schema instances.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier

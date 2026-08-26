# This is a numerical computation in exact linear algebra, the reconstruction of a

- **UUID:** `5884bca2-ccbc-41c9-90a4-999040938b95`
- **Slug:** `this-is-a-numerical-computation-in-exact-linear-algebra-the`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

This is a numerical computation in exact linear algebra, the reconstruction of a univariate polynomial from a scheme of derivative conditions. Each problem fixes a degree bound N, so the unknown polynomial has N coefficients and degree below N, together with a list of conditions.

Every condition is three integers, a point x, a derivative order j, and a value v, and it asks that the j-th derivative of the polynomial at x equal v, with the zeroth derivative being the value itself. The conditions are not required to be nicely shaped.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier

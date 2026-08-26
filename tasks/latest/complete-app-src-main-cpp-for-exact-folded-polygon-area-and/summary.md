# Complete /app/src/main.cpp for exact folded-polygon area and moments.

- **UUID:** `8824d7ea-ecc3-43dc-84c2-538720f26dc6`
- **Slug:** `complete-app-src-main-cpp-for-exact-folded-polygon-area-and`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Complete /app/src/main.cpp for exact folded-polygon area and moments. Legacy input is n, n counterclockwise integer vertices, then a b c defining a*x+b*y=c.

S is the closed a*x+b*y<=c portion; F is the reflection of the a*x+b*y>=c portion. Output visible_area, double_covered_area, visible_x_moment, visible_y_moment, double_x_moment, and double_y_moment, where visible is S union F and double is S intersection F.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier

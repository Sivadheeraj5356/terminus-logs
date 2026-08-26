# The annex-39 JWT lab under /app/environment builds witnesses that look fine on s

- **UUID:** `b3b1041b-59ad-4e1e-87aa-46f898bb2d8e`
- **Slug:** `the-annex-39-jwt-lab-under-app-environment-builds-witnesses`
- **Category:** security
- **Difficulty:** hard

## Summary

The annex-39 JWT lab under /app/environment builds witnesses that look fine on smoke instances, but independent certificate replay fails on the same tokens under finite context. Infer a specification consistent with the observable traces and repair Ruby module sources under /app/environment so library and module-level behavior is correct, not only checker CLI output.

Static or hand-written /app/output artifacts are insufficient; the normal build_lab.sh plus k9_verify pipeline must regenerate graded outputs. Edits without rebuild, or test changes, do not count.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier

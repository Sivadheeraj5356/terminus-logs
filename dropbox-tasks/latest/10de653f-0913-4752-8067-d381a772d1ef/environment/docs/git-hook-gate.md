# Git hook gate

Hook script: /app/hooks/pre-commit
The hook invokes /app/bin/reelseal hook-check.

A commit that stages /app/output/encryption-manifest.json must be rejected when validation-stamp.json is missing or accepted=false. Operators run hook-check explicitly during the desk flow; the hook mirrors the same validator.

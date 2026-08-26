# # Build the `foldpath` continuation command

- **UUID:** `757876fb-ab33-40a2-b881-877eea29883a`
- **Slug:** `build-the-foldpath-continuation-command`
- **Category:** scientific-computing
- **Difficulty:** hard

## Summary

Extend the C11 toolkit in `/opt/foldpath` with a native executable at `/usr/local/bin/foldpath`. Keep `/usr/local/bin/foldmodel-check` installed and working.

`make clean all install` must build both as regular native executables from source; do not replace either command with a script or symlink. Implement the complete observable contract below.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier

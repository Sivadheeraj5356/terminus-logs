# # Fleet unit constraint synthesizer

- **UUID:** `fdd2c545-ffae-43e4-8859-124485be6134`
- **Slug:** `fleet-unit-constraint-synthesizer`
- **Category:** system-administration
- **Difficulty:** hard

## Summary

The fleet synthesizer under `/app/environment` turns a declarative manifest plus overlay files into a verified systemd unit bundle and a deterministic restart trace. The pipeline currently mis-merges policy layers, mis-maps list fields into unit files, mis-labels slice entries, and simulates restart ordering incorrectly.

Repair the Rust resolver, Go emitters, Go trace simulator, and tarball packer so the normal rebuild path produces correct outputs. Run `bash /app/environment/scripts/build.sh` after source edits, then regenerate artifacts with:

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier

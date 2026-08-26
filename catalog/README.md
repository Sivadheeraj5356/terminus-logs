# Catalog notes

Built from the private Dropbox dump `terminal-bench-tasks.zip`, not from public Terminal-Bench 2.

- One catalog card per submission UUID (latest revision only).
- Older `*_submission_*.zip` files are revision history, not extra tasks.
- Archives are task packages (`instruction.md`, `task.toml`, Docker, oracle, tests).
- They do not include Harbor `result.json` or agent trajectories, so stump % is unknown until local Harbor jobs exist.
- Rebuild: `python scripts/unpack_dropbox.py` then `python scripts/build_catalog.py`.

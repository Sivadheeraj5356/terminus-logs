# Catalog notes

Built from the private `terminal-bench-tasks.zip` archive, not from public Terminal-Bench 2.

- One catalog card per submission UUID (latest revision only).
- Older `*_submission_*.zip` files are revision history, not extra tasks.
- Harbor packages live in [`../tasks/latest/`](../tasks/latest/) under catalog slugs (`instruction.md`, `task.toml`, Docker, oracle, tests, plus `summary.md`).
- They do not include Harbor `result.json` or agent trajectories, so stump % is unknown until local Harbor jobs exist.
- Rebuild: `python scripts/unpack_tasks.py` then `python scripts/build_catalog.py`.

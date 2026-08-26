# Workspace migrate lab

Local offline monorepo used to exercise release-train selection, package
extension peer closure, and content-addressed store sealing.

Driver: `pnpm run verify:all` (resume → seal → offline frozen install → build → audit).
Contract docs live under `docs/`.

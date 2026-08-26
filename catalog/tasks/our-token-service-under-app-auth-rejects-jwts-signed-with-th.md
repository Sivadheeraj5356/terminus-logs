# Our token service under `/app/auth` rejects JWTs signed with the retiring key ev

Submission: `40e57f12-6376-4580-b652-323845c350bb`  
Slug: `our-token-service-under-app-auth-rejects-jwts-signed-with-th`  
Latest archive: `40e57f12-6376-4580-b652-323845c350bb_submission_2026-07-09T08_28_54.503Z.zip`  
Revisions in Dropbox: 2

## Task summary

Our token service under `/app/auth` rejects JWTs signed with the retiring key even though we are still inside the rotation grace window. The full JWK rules live in `/app/auth/docs/jwk-rotation.md`. Fix kid lookup and grace handling in `/app/auth/cmd/tokensvc` and `/app/auth/internal/jwk`. While grace is open, tokens signed with either the active or retiring published key must validate when the header `kid` matches. The grace window includes its last second: at `rotated_at + grace_seconds` the retiring key must still work; one second later it must not. After grace, only the active key may validate.

Required artifacts include: `/app/auth`, `/app/auth/docs/jwk-rotation.md`, `/app/auth/cmd/tokensvc`, `/app/auth/internal/jwk`, `/app/auth/keys/rotation-state.json`, `/app/auth/config/service.toml`, `/app/auth/bin/build.sh`, `/app/auth/bin/tokensvc.sh`.

Author Anonymous tagged this **hard** security task (jwt, jwk, sqlite, rotation, revocation).

Time estimates: expert ~120.0 min, junior ~300.0 min.

Harbor timeouts: agent Nones, verifier Nones.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `40e57f12-6376-4580-b652-323845c350bb_submission_2026-07-09T08_28_54.503Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`

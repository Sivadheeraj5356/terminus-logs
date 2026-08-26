The Obsidian Vault WEBrick service at `/app` failed pen testing against the security contract in `/app/docs/api_spec.md`. Incident write-ups and exploit notes live in `/app/docs/vault_design_dossier.md`.

Close the open vulnerabilities so the service matches that contract:

- Admin debug and force-unlock paths must reject unsigned, forged, expired, and replayed requests (HMAC-SHA256, timestamp window, nonce store).
- Moderator verbs must require a valid body signature; unauthenticated privilege escalation must fail.
- Puzzle attempt evaluation must be race-safe so concurrent clients cannot overspend `attempts_remaining` or bypass prerequisites.
- Answer and vault comparisons must use the mandated digest; weak hashing is out of compliance.
- Per-IP rate limiting on `/command` must enforce the configured RPM and return 429 when exceeded.
- Required secrets and limits in `/app/config/settings.yaml` must be present and non-empty.
- Player-facing routes (`/state`, `/hint`, `/command`, `/session/new`, `/health`) must remain reachable for legitimate play.

Also finish the Go security regression suite under `/app/prop_test/`: implement the server harness and the five stubbed tests so they exercise the hardened controls over live HTTP. Harness launch requirements, fuzz depth, and concurrency invariants are specified in `/app/docs/vault_design_dossier.md` §7.4 (and the API behaviour in `/app/docs/api_spec.md`). From `/app/prop_test`, confirm with `go test -v -count=1 -timeout 120s ./...`.

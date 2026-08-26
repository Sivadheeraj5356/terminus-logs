The release-gate service under `/app/src/` is incomplete. It accepts evaluation requests over HTTP and is supposed to decide whether a signed Git release tag is eligible for promotion, but currently approves everything. Fix the implementation so it correctly enforces the policy.

The sole authority for policy behavior is `/app/standard/cdss_v4.md`. All decisions — how the compose model is assembled, how services are classified and evaluated, how policy obligations apply, how exception windows are consulted, and how key and hook requirements are verified — follow that document. The HTTP wire contract (endpoint definitions, request/response structure, and the database connection requirement) is in `/app/docs/api_contract.md`.

Build the service with `/app/build.sh`. The compiled artifact goes to `/app/bin/gate.jar`; runtime dependencies are vendored at `/opt/jars/`. Start it with `/app/scripts/run_gate.sh`, which serves `127.0.0.1:8971`. Do not modify either script.

`GET /health` returns exactly the bytes `{"status":"ok"}` with no trailing newline and `Content-Type: application/json`.

`POST /gate/evaluate` takes a JSON object with exactly three string keys: `repo` (absolute path to a repository root), `tag` (a full tag ref), and `evaluationTime` (an ISO-8601 UTC timestamp). Any request with a missing or extra key, a non-string value, or an unparseable `evaluationTime` responds with HTTP 400 and the body `{"error":"malformed request"}`. All evaluations — approvals and denials alike — respond with HTTP 200.

All temporal decisions use the `evaluationTime` from the request and the timestamps recorded in the git tag; the service must not consult the system clock.

The response body for all 200 decisions is a JSON object with two top-level keys: `decision` and `reasons`. Object keys at every level are sorted in ascending lexicographic byte order. When approved, `decision` is the string `"approve"` and `reasons` is an empty array. When denied, `decision` is `"deny"` and `reasons` is a non-empty array. Each element is an object with exactly three keys: `clauseId` (a clause identifier of the form `§X.Y`), `code` (a reason code of the form `CDSS-CATEGORY-NNN`), and `service` (the offending service name, or an empty string when the reason pertains to the repository or tag rather than a specific service). On denial, the reasons array is sorted first by `code` in ascending lexicographic order and then by `service` in ascending lexicographic order.

The service reads policy evidence from an H2 database on every request. The database file is at `/app/data/approvals.mv.db`, seeded from `/app/data/seed_approvals.sql`. The service opens a fresh read-only JDBC connection per request and closes it before sending the response; external tooling may modify the file between requests and those changes must be visible to the next request without a service restart. The service must not write to the database file.

The endpoint will be exercised against repositories, tags, database states, and exception-window configurations it has not seen during development — the implementation must derive every decision from the standard and live database state, not from knowledge of the shipped fixtures.

The fixture repositories are at `/app/repos/payments-stack` and `/app/repos/hook-broken`. The GPG keyring for tag-signature verification was imported at image build time and lives at `/root/.gnupg-cdss`.

Evaluation is entirely static: the service must not invoke `docker` or any container runtime and must not shell out to any script interpreter at request time. Repeated identical requests must produce byte-identical JSON responses. Do not modify `/app/standard/cdss_v4.md`.

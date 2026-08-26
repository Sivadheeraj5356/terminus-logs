# Injected defects (oracle reference — not shipped to participants)

1. `internal/hash` — DomainHash missing `\n` separator
2. `internal/graph` — Kahn ready queue sorted descending
3. `internal/policy` — config file re-applied after env (file wins)
4. `internal/parser` — NFKC instead of NFC; metadata keys inserted descending (workflow ID name+version payload is correct in the starter)
5. `internal/compiler` — dependency edges inverted; self-loop check skipped; orphan nodes dropped from order
6. `internal/scheduler` — workers descending; max_retries off-by-one (+1); timeout 0 not falling back to policy
7. `internal/executor` — executes reverse plan order; cache hit still re-executes
8. `internal/cache` — cache key omits workflow ID
9. `internal/journal` — journal hash uses descending seq order
10. `internal/state` — canonical save uses unsorted `json.Marshal`
11. `internal/checkpoint` — Latest selects lowest version; incremental merge overwrites completed/digests/metadata
12. `internal/recovery` — resumes from second-latest checkpoint; rollback skips orphan nodes
13. `internal/replay` — wall-clock RFC3339Nano timestamps; reverse event order; hash/match divergence
14. `internal/verification` — lineage walks children as parents; undirected graph equality; soft hash check
15. `internal/certificate` — domain `recovery-cert`; missing replay_hash binding; SHA256(body||token) not HMAC
16. `scripts/run_pipeline.sh` — VERBOSE=1 resets ROOT to `.` and forces STRICT_MODE=false

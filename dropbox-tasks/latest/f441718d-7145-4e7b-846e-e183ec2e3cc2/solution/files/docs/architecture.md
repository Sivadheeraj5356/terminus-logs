# Architecture Notes

## Machine-learning control plane

This is an offline **machine-learning** training control plane for supervised
model-training DAGs (feature ingest, train/eval, artifact publish). All I/O is
local filesystem mock storage. Stages communicate exclusively through JSON
artifacts under `state/` and `output/` so experiment lineage stays deterministic.

## Determinism rules

1. No `time.Now` in digest-bound paths.
2. No `math/rand` or `crypto/rand` for scheduling.
3. No network dials.
4. Maps are canonicalized before hashing.
5. Ready queues are sorted ascending by node ID.

## Failure model

Injected failures are controlled via `RUNTIME_FAIL_NODE` for operator drills.
Recovery always selects the highest checkpoint version and materializes a new
checkpoint with `version = previous + 1`.

## Certificate trust

Operators verify `output/certificate.json` using the HMAC token in
`configs/hmac_signing_token.txt`. The body must bind plan, journal, replay,
recovery, and verification digests.

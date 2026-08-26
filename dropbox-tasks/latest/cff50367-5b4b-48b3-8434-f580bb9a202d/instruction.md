# JWT JWKS Signing-Key Admission

Security operators on JWT/JWKS trust boundaries enforce signing-key admission
and revocation from local JWKS tier trees under `/app/environment/fixtures`.
During ordinary rotate, retire, and peer-realm inherit work, a short local
pulse probe can look fine while `/app/output/freshness-report.json` still
admits withdrawn kids, lets weaker cache/tenant material override stronger
issuer policy, drops inherited peer kids across the realm trust boundary, or
leaves a stale rotation seal in force. Those are authorization failures: a
retired signing kid must stay denied, stronger issuer policy must win, and
foreign-realm residue must not cross the active profile principal.

Implement JWT/JWKS signing-key admission controls under `/app/environment`
from the authorization specification in `/app/environment/docs/contract.md`
so `/app/bin/mux audit --profile <name>` regenerates
`/app/output/freshness-report.json` through the normal admission path for the
shipped `amber`, `beryl`, and `onyx` trust realms. Hand-written output is
rejected. The verifier may delete that artifact and rerun the command. An
advisory readiness probe is `/app/bin/mux pulse <name>`; it does not replace
audit and must not be trusted over the admission path. `onyx` inherits shared
keys from `beryl`, so beryl durable state must already exist when onyx is
audited.

Report shape, JWKS-tier ordering, companion recovery, generation-floor
filtering, deferred retracts (`effective_seq`), realm inheritance
(`inherits_from` / `shared_keys`), cross-run carry, digest rules, and epoch
seal writes are in that authorization specification. The report carries
profile, epoch, counter, runs, entries, and checkpoints. Runs include run_id,
phase, scope_digest, and previous_digest. Entries include key, value,
source_scope, origin, and observed_digest. Checkpoints include first_seq,
last_seq, record_count, epoch_floor, epoch_ceil, generation_floor, and
generation_ceil. Rows at the generation floor participate in reconciliation.
Carry uses mark greater than or equal to 0.5. A successful audit reseals
persisted epoch metadata with lowercase keys epoch, counter, seal_rev, and
tag. Retracted or withdrawn signing kids must not remain admitted after the
admission path converges.

Repeat JWT signing-key admissions must keep those authorization outcomes
stable across crash residue, out-of-order spill records, stale metadata,
malformed primary batches, owned residue from other realms, retract
companions, generation-floor staging, cross-run carry, deferred retract
boundaries, parent-realm inheritance, revision drift, and green pulse probes.
Verified reports must come from the implemented mux admission path, not
edited tests or wrapper-only bypasses.

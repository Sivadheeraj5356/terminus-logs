The `msgsigward` program under /app/environment is a complete RFC 9421 HTTP
message-signature verifier: `msgsig.Verify` in
/app/environment/internal/msgsig/verify.go reads one immutable request bundle and
prints the decision line `<verdict> <selector> <covered>` an HTTP server uses
before acting on a signed request. The implementation is finished and builds, but
it is **not** faithful to its specification: it contains several planted security
defects, each a divergence from /app/environment/docs/security-spec.md that lets a
forged, under-covered, replayed, body-substituted, or algorithm-downgraded request
through — or misreports which rejection applies. The evidence is immutable: audit
the code against the spec; do not modify the verifier or the tests.

Your deliverable is /app/environment/findings.json. For **every** defect in the
shipped verifier, include one *witness*: a complete request bundle (the same JSON
schema `msgsigward` consumes, described in the spec's §1) on which the shipped
verifier's decision is **insecure** — that is, it diverges from the decision the
specification requires. A witness that makes the shipped verifier accept a request
the spec rejects (a forgery slipping through), reject a request the spec accepts (a
genuine request broken by a reconstruction error), or report the wrong rejection
reason each expose a distinct defect. Cover them all; a findings file that misses
any planted defect is incomplete.

Write findings.json as:

```json
{ "findings": [
  { "defect": "<short label you choose>", "witness": { <a full request bundle> } },
  ...
] }
```

You may build and run `msgsigward` on inputs you construct to confirm each witness
actually triggers the defect. Grading is behavioral: each witness is replayed
through the shipped verifier and compared against an independent, spec-faithful
oracle; the audit is complete only when the witnesses expose every planted defect.
Example request bundles with their spec-correct decisions are under
/app/environment/testdata/examples. The signatures are standard ed25519 and
HMAC-SHA256 (Go standard library), so a witness that must carry a valid signature
can be constructed with `crypto/ed25519`, `crypto/hmac`, and `crypto/sha256`.

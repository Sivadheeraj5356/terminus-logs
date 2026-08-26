The gateway snapshot in `/app` contains an inert Go `main` package where its
authorization engine should be. Complete that package so the resulting binary
can decide a stream of service-mesh requests backed by primary macaroons and
arbitrarily nested third-party discharges.

This is a stateful proof-verification problem. The implementation must rebuild
the chained HMACs, bind every discharge both to the primary proof and its exact
parent edge, find the globally canonical assignment of single and threshold-
quorum discharge tokens, evaluate normalized request caveats, and update
persistent nonce and single-use proof state in request order. A discharge that
is valid in isolation is not authorization unless it is attached at the correct
place in the proof tree; unused, replayed, duplicate-identity, partially bound,
and nested dead-end evidence must be handled exactly as specified.

The authoritative rules are in `/app/MACAROON_CONTRACT.md`, including
normalization, key lifetimes, signature construction, nested assignment,
failure precedence, state transitions, ordering, and the exact JSON shape.
Compatible evaluation inputs change the requests, key rings, caveat graph, and
discharge ordering, so derive every decision from the supplied data.

During verification, the Go package is compiled to `/app/macaroon-audit`. When
run from `/app`, it must read `/app/input/inspection.json`, create or replace
`/app/output/report.json`, and leave the input untouched. Keep the decision
engine self-contained in the compiled Go program; it may not delegate work to
an interpreter, helper process, or network service.

# Stage Contract Summary

This document summarizes cross-stage invariants that must hold after a successful A→H run.

## Identity

- Workflow ID derives from NFC-normalized name **and** version joined by `"\n"`.
- DomainHash always inserts a single newline between domain and payload.
- Plan digest binds workflow ID, topo order, and directed edges.
- Journal hash binds workflow ID and ascending-seq wire entries `{action,digest,meta,node_id,seq}`.

## Ordering

- Topological order uses lexicographically smallest ready node.
- Scheduler assigns workers in ascending worker ID order.
- Executor runs plan order exactly.
- Replay events are ascending by seq.

## Recovery

- Latest checkpoint is maximum version.
- Incremental merge unions completed sets and overlays digests/metadata.
- Recovery resumes failed and incomplete nodes, including orphans.

## Certificate

- Body includes replay_hash.
- Body digest domain is `recovery-certificate-v1`.
- Signature is HMAC-SHA256(token, canonical body).

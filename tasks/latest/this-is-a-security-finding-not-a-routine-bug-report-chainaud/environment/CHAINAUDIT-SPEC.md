# ChainAudit Engineering Specification

## Tamper-Evident Audit Log: Verification, Compaction, and Retention

| | |
|---|---|
| **Status** | Living document |
| **Doc ID** | DICE-RFC-0031 |
| **Current version** | 1.9.0 — see Section 16, Changelog, for full revision history |
| **Owning team** | Data Integrity & Compliance Engineering (DICE) |
| **Authors** | Priya Ramaswamy (DICE, original author), Marcus Oyelaran (DICE / SRE liaison), Dana Whitfield (Compliance Engineering) |
| **Reviewers** | Alex Feng (Security Engineering), Ingrid Voss (Key Management team), Rahul Deshmukh (Legal Engineering) |
| **First published** | 2024-03-04 |
| **Last substantive revision** | 2025-05-27 |

> This document is the canonical specification for ChainAudit: the byte-level encoding of every hashed structure, the Merkle and checkpoint-chain construction, the checkpoint signing contract, the external key-management HTTP contract, and the retention and legal-hold policy that governs pruning. It is maintained by DICE and reviewed jointly with Security Engineering, the Key Management team, and Legal Engineering whenever the wire format, the KMS contract, or the retention rules change. If you are implementing, debugging, or operating any part of ChainAudit, this document — not tribal knowledge, not a prior implementation's behavior, not what a script happened to do last Tuesday — is the source of truth. Where the running code and this document disagree, that is a bug in the code (or, occasionally, a bug in this document — file an amendment per the process in Section 16's header note).

---

## Table of Contents

1. [Overview and Scope](#1-overview-and-scope)
2. [System Architecture](#2-system-architecture)
3. [Data Model](#3-data-model)
4. [Canonical Encoding Specification](#4-canonical-encoding-specification)
5. [Merkle Tree Construction](#5-merkle-tree-construction)
6. [Genesis and the Checkpoint Tip Chain](#6-genesis-and-the-checkpoint-tip-chain)
7. [Checkpoint Signing Contract](#7-checkpoint-signing-contract)
8. [Key Management Service API Reference](#8-key-management-service-api-reference)
9. [Tombstones and Right-to-Erasure Semantics](#9-tombstones-and-right-to-erasure-semantics)
10. [Legal Hold and Retention Policy](#10-legal-hold-and-retention-policy)
11. [Schema Versioning and the v1 → v2 Migration](#11-schema-versioning-and-the-v1--v2-migration)
12. [CLI Reference](#12-cli-reference)
13. [JSON Output Schema Appendix](#13-json-output-schema-appendix)
14. [Operational FAQ / Troubleshooting](#14-operational-faq--troubleshooting)
15. [Error Codes and Diagnostics Appendix](#15-error-codes-and-diagnostics-appendix)
16. [Changelog / Dated Amendment History](#16-changelog--dated-amendment-history)

---

## 1. Overview and Scope

ChainAudit is the internal command-line tool the compliance team uses to verify and prune the tamper-evident audit logs that back regulatory and contractual retention commitments. Each audit log is a per-stream, strictly-ordered sequence of events — a login, a permission change, a data export, a support agent's access to a customer record, a right-to-erasure fulfillment — stored as rows in a SQLite database file. The defining property of these logs is not that they are hard to read or hard to reach; access control is somebody else's job and is enforced upstream of ChainAudit entirely. The defining property is that *if a row is altered after the fact, that alteration is detectable*, and that detection does not depend on trusting the database file itself, the filesystem it sits on, or the operator running the check. It depends only on independently-held cryptographic material (a small number of HMAC keys, held by a separate Key Management service) and arithmetic anyone can redo by hand.

ChainAudit ships exactly two subcommands: `verify`, which walks a database and produces a signed-and-checked report of every stream's integrity status, and `compact`, which prunes event rows that have aged out of their stream's retention window and are not otherwise protected by legal hold — without ever discarding the cryptographic ability to prove what was pruned once existed unmodified. Both subcommands are read-heavy, single-machine, single-invocation batch tools. Neither is a server; neither holds state between invocations beyond what is in the SQLite file and, for `compact`, a single reference timestamp supplied on the command line. There is no daemon, no polling loop, and no persistent process.

This document describes the complete on-disk data model, the exact byte-for-byte construction of every hash used anywhere in the system, the external key-management contract `verify` depends on, the retention and legal-hold rules `compact` enforces, and the JSON report formats both subcommands emit. It is written at the level of detail needed to re-derive every hash in this system by hand from raw bytes, because that level of precision is the entire point of the tool: a "close enough" reimplementation of a hash-chained audit log is worse than useless, since it will either flag good data as corrupt or, far more dangerously, fail to flag corrupt data as corrupt.

### 1.1 What ChainAudit is not

ChainAudit does not write events or create checkpoints. Ingestion — appending a new event row, computing and storing its `leaf_hash`, and periodically rolling a full batch of events into a signed checkpoint — is performed by a separate service (the audit-ingest pipeline) that is out of scope for this document except insofar as its output format (the schema in Section 3, the encoding in Section 4, the signing contract in Section 7) is exactly what `verify` and `compact` consume. If you are debugging why a stream has no checkpoints yet, or why a checkpoint's `key_id` points at a key you don't recognize, the ingest pipeline's own runbook is the right place to look; this document only describes what ChainAudit does with rows and checkpoints once they exist.

ChainAudit does not encrypt payloads at rest, does not manage access control on the SQLite file, does not perform real-time alerting or intrusion detection, and does not implement a distributed consensus protocol. It is a single-writer-at-a-time, single-file, batch integrity and retention tool. It assumes the SQLite file it is pointed at is the one the ingest pipeline has been writing to, and it assumes exclusive access for the duration of a single invocation (see Section 2.4 on concurrency).

ChainAudit does not decide *whether* a right-to-erasure request should be honored, or *whether* a piece of data should be placed under legal hold. Those are decisions made by the compliance and legal teams through their own case-management tooling, which then writes the resulting flags (`tombstone`, `legal_hold` at the event level, `legal_hold` at the stream level) into the rows ChainAudit reads. ChainAudit's job is to encode those flags correctly into the hash chain (so that erasure and legal hold are themselves tamper-evident facts, not silent database edits) and to enforce the resulting retention arithmetic precisely and conservatively.

### 1.2 Design goals, in priority order

1. **Independent verifiability.** Anyone with the SQLite file, network access to the Key Management service, and this document should be able to redo every check ChainAudit performs, by hand if necessary, and get the same answer. No check in this system should depend on information that only ChainAudit's own prior output can supply.
2. **Conservative pruning.** It is always acceptable for `compact` to retain a batch it could theoretically have pruned. It is never acceptable for `compact` to prune a batch it should have retained. Every ambiguous case in Section 10 resolves toward retention.
3. **Detection over prevention.** ChainAudit does not stop anyone with direct database access from editing a row. It guarantees that if they do, a subsequent `verify` run will notice, and will be able to say precisely which row (`first_bad_seq`) or which checkpoint (`first_bad_batch`) is inconsistent with the signed history.
4. **Erasure without breaking the chain.** The system must support legitimate, compliance-mandated deletion of a specific event's payload (right-to-erasure) without that deletion looking indistinguishable from tampering, and without invalidating the tamper-evidence of every event around it. Section 9 covers this in depth; it is the single trickiest property in the whole design and has its own incident history in Section 16.
5. **No silent trust in a revoked key.** If the key that signed a checkpoint has since been rotated out, ChainAudit must say so plainly and distinctly from saying the checkpoint is corrupt — but it must never use "the key is gone" as an excuse to skip checks it is still capable of performing. See Section 8.3 for the full treatment of this distinction; it is the second trickiest property in the system.

### 1.3 Audience

This document is written for engineers who maintain the ChainAudit codebase, for SREs who operate it against production databases, and for compliance engineers who consume its JSON output as part of audit evidence packages. It assumes familiarity with SHA-256, HMAC, Merkle trees in the abstract, and Go, but does not assume prior familiarity with this specific system's byte layouts — those are derived from first principles below, with worked numeric examples at every layer, precisely so that nothing here needs to be taken on faith.

### 1.4 Relationship to other internal documents

The audit-ingest pipeline (which writes `streams`, `events`, and `checkpoints` rows) has its own design document, DICE-RFC-0022, referenced here only where its output format matters to ChainAudit. The Key Management service's full API surface (key creation, rotation scheduling, access policy) is documented by the Key Management team in their own service doc; Section 8 of this document reproduces only the read-path contract (`GET /v1/keys/{key_id}`) that ChainAudit depends on, and reproduces it in full because a stale or approximate description of an external contract is a common source of exactly the kind of bug this tool exists to catch elsewhere.

---

## 2. System Architecture

### 2.1 Components

ChainAudit as delivered is a single statically-linked Go binary with two subcommands. Conceptually, though, four things participate in every `verify` run and three in every `compact` run:

```
                          ┌────────────────────────┐
                          │   SQLite database file   │
                          │ (streams / events /       │
                          │  checkpoints tables)      │
                          └────────────┬──────────────┘
                                       │ read-only (verify)
                                       │ read + narrow delete (compact)
                                       ▼
   ┌───────────┐        ┌──────────────────────────┐        ┌────────────────────┐
   │ chainaudit │◄──────►│  internal/chainstate       │        │  Key Management     │
   │  verify     │        │  (canonical encoding,      │        │  service (external,  │
   │  compact    │        │   Merkle math, genesis/    │        │   HTTP, owned by the │
   └───────────┘        │   tip chain, signing bytes)│        │   Key Management team)│
                          └──────────────────────────┘        └─────────┬───────────┘
                                                                          │ GET /v1/keys/{key_id}
                                                             ┌────────────┴────────────┐
                                                             │ verify only — compact     │
                                                             │ never calls the KMS       │
                                                             └───────────────────────────┘
```

- **The SQLite database file** is produced and maintained by the audit-ingest pipeline. ChainAudit treats it as an input (for `verify`) or as an input-and-narrowly-mutated-output (for `compact`). ChainAudit never creates the `streams`, `events`, or `checkpoints` tables — if they don't exist, both subcommands fail fast rather than attempting to initialize a schema, because a missing table on a production compliance database is far more likely to indicate the wrong file was passed than a fresh install.
- **`internal/chainstate`** is the Go package, internal to the ChainAudit module, that owns every piece of cryptographic construction described in Sections 4 through 7: canonical event encoding, leaf and internal-node hashing, Merkle tree folding, genesis derivation, tip-chain folding, and checkpoint-signing-byte construction. Both `verify` and `compact` import it; neither reimplements any part of it locally.
- **The Key Management service** is an external HTTP service, owned by a separate team, that resolves a `key_id` to raw HMAC key material (or reports that the key has been rotated out). Only `verify` talks to it — `compact` has no cryptographic need to, since pruning decisions depend only on timestamps and hold flags, never on signature validity. See Section 8.
- **The `chainaudit` binary** itself is thin: `verify.go` and `compact.go` are almost entirely SQL orchestration (deciding what to read, in what order, and what to do with the result) plus JSON marshaling of the report. Neither file contains a SHA-256 call, a Merkle-folding loop, or an HMAC computation of its own; all of that routes through `chainstate`.

### 2.2 Why chain-state computation is centralized in one package

This is worth dwelling on, because it is the single architectural decision most responsible for this system being trustworthy rather than merely plausible-looking.

`verify` and `compact` are invoked separately, at different times, often by different people or different cron schedules, against the same database. The entire value of the `chain_tip_hash` field described in Section 6.4 — the invariant that a `verify` report's `chain_tip_hash` for a stream and a `compact` manifest's `chain_tip_hash` for that same stream, computed immediately before and after a compaction, are byte-identical — depends on both subcommands computing that value the *same way*, down to the byte. If `verify.go` and `compact.go` each contained their own hand-rolled copy of the tip-chain folding logic, it would be entirely possible for the two implementations to drift: an off-by-one in how one of them serializes `batch_index`, a different choice of big-endian versus little-endian in the other, a forgotten field in one but not the other. Each copy might even be internally self-consistent and pass its own narrow checks while silently disagreeing with the other. The failure mode of that drift is not a crash. It is `compact` reporting a `chain_tip_hash` that `verify` would never produce for the same stream state, which either erodes trust in a perfectly good compaction or — worse — papers over a real inconsistency because nobody is cross-checking the two independently.

Centralizing every hash construction in `internal/chainstate`, and requiring both subcommands to call into it rather than reimplement it, converts "these two tools must independently arrive at the same answer" into "these two tools must call the same function." The second property is trivially true by construction; the first is not, and is exactly the kind of thing that erodes silently over months of independent maintenance if not structurally prevented. This is also why `chainstate` has no dependency on either `verify.go` or `compact.go` — the dependency arrow only ever points one way, from the two subcommands down into the shared package, never sideways between the subcommands themselves. Neither subcommand should ever need to know the other exists.

At a conceptual level (this document describes behavior, not Go signatures, but the shape of the package's exported surface is useful context for orienting anyone reading the source alongside this spec), `chainstate` exposes one function per construction defined in Sections 4 through 7, and nothing else:

- A canonical-encoding function taking an event's fields (plus the owning stream's `migrated_at`, since version selection needs it) and returning the exact byte sequence from Section 4.3.
- A leaf-hash function, layered directly on top of the encoding function, implementing Section 4.4.
- A Merkle-fold function taking an ordered list of leaf hashes and returning a root, implementing the RFC 6962 recursion in Section 5.1 — the one and only place the "largest power of two strictly less than n" logic exists anywhere in the codebase.
- A genesis function taking a `stream_id` and returning Section 6.1's output.
- A tip-fold function taking a previous tip and one checkpoint's fields and returning the next tip, implementing Section 6.2.
- A signing-bytes function taking a checkpoint's coordinates and root and returning Section 7.1's byte sequence — deliberately *not* itself performing the HMAC computation, which stays in the KMS-client-adjacent code path in `verify` that actually holds key material, so that `chainstate` itself never needs to import or reason about cryptographic keys at all, only about the (unkeyed) byte layouts that get signed or hashed.

Every one of these functions is pure — no I/O, no database access, no network calls — which is precisely what makes it possible to unit-test `chainstate` exhaustively against the worked examples in this document without needing a database or a running KMS at all, and what makes the worked hex values throughout Sections 4 through 7 directly checkable against the running implementation rather than merely illustrative.

### 2.3 Local and staging use: the mock KMS

Because `verify` has a hard runtime dependency on the Key Management service's HTTP contract, and because that contract includes behaviors (a `410 Gone` for a rotated key, a `429` under load) that are awkward or impossible to reliably trigger against the real production KMS on demand, the repository also ships a small reference server, `mockkms`, under `cmd/mockkms`. `mockkms` implements exactly the read-path contract described in Section 8 — `GET /v1/keys/{key_id}` — against a small static or file-backed table of key IDs, each configured to return a `200` with specific key material, a `410`, or (for exercising retry logic) a `429` for the first N requests before flipping to a `200`.

`mockkms` is not a stub that merely returns a fixed `200` for anything asked of it; it is a faithful implementation of the same three-status-code contract real KMS clients must handle, and it is what engineers point `--kms-addr` at when developing or operating against a staging database, or when rehearsing what a stream's `verify` output looks like once a specific key is rotated out. Treat its responses as authoritative for the shape of the contract — if `mockkms` and this document ever disagree about response shape, that is a bug in one of the two, and this document wins (file an amendment).

`mockkms` deliberately has no write path, no authentication, and no persistence beyond its static configuration; it exists to let `verify` be run against a KMS-shaped endpoint without depending on the production Key Management service's availability, credentials, or rate limits, and its configuration format is documented separately in the `mockkms` package's own comments rather than here, since it is operational tooling rather than part of the wire contract itself.

### 2.4 Concurrency and file access assumptions

ChainAudit opens the SQLite file directly (not through a network-facing database server), and assumes it has exclusive write access for the duration of a `compact` run and stable read access for the duration of a `verify` run. Both subcommands open the database in a single connection; `compact` wraps its entire per-stream pruning decision and the corresponding `DELETE` in a single SQLite transaction per batch (see Section 10.5), so that a crash or kill mid-run leaves the database in a state consistent with *some* prefix of the intended work, never a state where a batch is half-deleted. ChainAudit does not itself coordinate with the audit-ingest pipeline's writers; operational practice is to run `verify` and `compact` during ingest-quiet windows or against a snapshot, and that coordination lives in the operational runbook, not in this document's technical contract. If `compact` observes a `SQLITE_BUSY` condition it surfaces the error and exits non-zero rather than retrying indefinitely — an audit-log pruning tool that silently retries against a lock for an unbounded time is a worse operational failure mode than one that stops and says so.

### 2.5 What `verify` reads and writes

`verify` opens the database read-only at the SQLite connection level (`?mode=ro` in the DSN) and performs no writes to it under any circumstances, including when it detects corruption — flagging corruption is not the same as fixing it, and `verify` never attempts the latter. Its only output is the JSON report described in Section 13.1, written to the path given by `--out`. If `--out` cannot be created or written, `verify` fails before completing (it does not partially write a report and exit 0).

### 2.6 What `compact` reads and writes

`compact` reads `streams`, `events`, and `checkpoints`, and writes to exactly one table: it issues `DELETE FROM events WHERE stream_id = ? AND seq BETWEEN ? AND ?` for each batch it determines is eligible for pruning, and nothing else. It never inserts, updates, or deletes rows in `streams` or `checkpoints`. It never modifies `leaf_hash`, `payload`, `tombstone`, or `legal_hold` on any surviving row. Its only other output is the JSON manifest described in Section 13.2, written to the path given by `--out`.

This narrow mutation surface is deliberate and load-bearing: because `compact` can only ever delete whole ranges of `events` rows and nothing else, every other input to every hash construction in this system (checkpoint `merkle_root`, checkpoint `signature`, stream `checkpoint_interval`, stream `migrated_at`) is invariant across a `compact` run by construction, not merely by convention. This is precisely why `chain_tip_hash` is guaranteed stable across pruning — see Section 6.4.

## 3. Data Model

### 3.1 Overview

ChainAudit's entire world is three SQLite tables: `streams`, `events`, and `checkpoints`. Every check `verify` performs and every deletion `compact` performs is a function of the rows in these three tables and nothing else — no configuration file, no environment variable, and no external state (other than the Key Management service's answer to "is this key still active") feeds into either subcommand's decisions. This is intentional: an audit tool whose behavior depends on hidden state is an audit tool nobody can independently check.

```sql
CREATE TABLE streams (
  stream_id TEXT PRIMARY KEY,
  migrated_at INTEGER,              -- NULL = stream has never been migrated to v2 (pure v1 legacy)
  checkpoint_interval INTEGER NOT NULL,
  retention_days INTEGER NOT NULL,
  legal_hold INTEGER NOT NULL DEFAULT 0,   -- whole-stream legal hold: 1 exempts every batch from pruning
  created_at INTEGER NOT NULL
);

CREATE TABLE events (
  stream_id TEXT NOT NULL REFERENCES streams(stream_id),
  seq INTEGER NOT NULL,             -- 0-indexed, monotonic per stream
  ts INTEGER NOT NULL,              -- unix seconds
  event_type TEXT NOT NULL,
  payload BLOB,
  tombstone INTEGER NOT NULL DEFAULT 0,
  legal_hold INTEGER NOT NULL DEFAULT 0,   -- per-event legal hold
  leaf_hash BLOB NOT NULL,          -- computed once at ingestion time, never recomputed in place
  PRIMARY KEY (stream_id, seq)
);

CREATE TABLE checkpoints (
  stream_id TEXT NOT NULL REFERENCES streams(stream_id),
  batch_index INTEGER NOT NULL,     -- 0-indexed, one per full batch of checkpoint_interval events
  start_seq INTEGER NOT NULL,
  end_seq INTEGER NOT NULL,
  merkle_root BLOB NOT NULL,
  signature BLOB NOT NULL,          -- HMAC-SHA256 over CheckpointSigningBytes, see Section 7
  key_id TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  PRIMARY KEY (stream_id, batch_index)
);
```

Every timestamp column in this schema (`streams.migrated_at`, `streams.created_at`, `events.ts`, `checkpoints.created_at`) is unix seconds, not milliseconds, and not an SQLite `DATETIME` string. There is no timezone stored or implied anywhere in this schema; unix seconds are timezone-free by construction, and every place this document computes or compares a timestamp, it does so in UTC-equivalent unix-seconds arithmetic. Do not let a client library's convenience wrapper silently convert one of these integers into a `time.Time` in the host's local timezone and back — that round-trip is lossless for the *instant* represented but has caused real confusion (see Section 16, 2024-10-21 entry) when engineers eyeballed a raw integer and mentally converted it using the wrong zone.

### 3.2 The `streams` table

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `stream_id` | TEXT | No (PK) | The stream's stable identifier. See Section 3.2.1 for charset and length rules. |
| `migrated_at` | INTEGER | Yes | Unix seconds. `NULL` means this stream has never undergone the v1→v2 migration described in Section 11 — every event ever ingested into it, and every event that will ever be ingested into it in the future, is encoded as v1. A non-`NULL` value is the timestamp after which newly-ingested events are encoded as v2; it does not retroactively change how already-stored events were encoded (see Section 4.2). |
| `checkpoint_interval` | INTEGER | No | The number of consecutive events that make up one checkpoint batch for this stream. Fixed at stream creation (see Section 3.2.2). There is no system-wide default and no fallback constant anywhere in ChainAudit — every `streams` row carries its own explicit value, and any code path that would need a checkpoint interval for a stream must read it from this column or fail; it must never assume a value. |
| `retention_days` | INTEGER | No | The number of days a fully-present, non-legal-held event must age past before its containing batch becomes eligible for pruning. See Section 10. |
| `legal_hold` | INTEGER | No, default 0 | Whole-stream legal hold. `1` means every batch belonging to this stream is exempt from pruning, unconditionally, regardless of age or per-event legal hold state. See Section 10.2. |
| `created_at` | INTEGER | No | Unix seconds; when the stream row was first created by the ingest pipeline. Informational only — no check in this document reads `streams.created_at` for any decision. |

#### 3.2.1 `stream_id` charset and length

`stream_id` is an opaque, case-sensitive UTF-8 string chosen by the system that owns the events being audited (a service name, a tenant identifier, a compound key — the convention is up to the producer and is not constrained by ChainAudit beyond what the encoding format can represent). Because `stream_id` is length-prefixed with a 2-byte big-endian field everywhere it appears in a hashed structure (Section 4.3, Section 7.1), its **UTF-8-encoded byte length**, not its character count or code-point count, must fit in an unsigned 16-bit integer: 0–65,535 bytes. A `stream_id` containing multi-byte UTF-8 characters (for example, characters outside the ASCII range) can have a byte length considerably larger than its character count; always measure and prefix the encoded byte length, never the rune count. This distinction has bitten a client implementation before — see the 2025-01-06 changelog entry.

#### 3.2.2 `checkpoint_interval` is immutable after creation

`checkpoint_interval` is read once when a stream begins ingesting and is not intended to change for the lifetime of that `stream_id`. Nothing in the schema technically prevents an `UPDATE streams SET checkpoint_interval = ...` — SQLite will happily execute it — but doing so would desynchronize the interval from every checkpoint already cut under the old value, since each checkpoint's `start_seq`/`end_seq` span was fixed at creation time using whatever interval was in effect then. ChainAudit relies on the *stored* `start_seq`/`end_seq` on each checkpoint row as authoritative — it does not recompute batch boundaries from `checkpoint_interval` on the fly — but it does use `checkpoint_interval` as a structural sanity check (Section 3.5.3): every checkpoint's span, `end_seq - start_seq + 1`, is expected to equal the stream's current `checkpoint_interval`. If an operator ever needs a different cadence, current tooling's answer is to start ingesting under a new `stream_id`, not to mutate `checkpoint_interval` on an existing one. This was not always the design; see the 2024-07-15 changelog entry for the story of why `checkpoint_interval` is a per-stream column at all rather than a single global constant.

### 3.3 The `events` table

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `stream_id` | TEXT | No (PK part, FK) | References `streams.stream_id`. |
| `seq` | INTEGER | No (PK part) | 0-indexed, strictly monotonic per stream, assigned by the ingest pipeline in ingestion order. There are no gaps in a healthy stream: for a stream with `N` events ever ingested (including any that have since been pruned), the full historical `seq` range is exactly `0..N-1`. Pruning removes rows but never renumbers survivors — `seq` values are permanent identifiers, not positions in a currently-present list. |
| `ts` | INTEGER | No | Unix seconds. The event's own timestamp, assigned at ingestion. This is the timestamp compared against `streams.migrated_at` for version selection (Section 4.2) and against the retention window for pruning eligibility (Section 10.3). It is emphatically not the same value as `checkpoints.created_at` or `streams.created_at`, and there is no guarantee `ts` values are strictly increasing in lockstep with wall-clock ingestion time down to the second (two events can share a `ts`) — only that `seq` order matches ingestion order. |
| `event_type` | TEXT | No | A free-text classifier chosen by the event producer (`"user.login"`, `"user.delete_request"`, and so on). ChainAudit does not validate `event_type` against any enum or registry; it is hashed as opaque UTF-8 bytes like every other string field. |
| `payload` | BLOB | Yes | The event's application-level payload. May legitimately be `NULL` or zero-length for event types that carry no payload (a heartbeat, a request that failed validation before any payload was recorded). Once `tombstone = 1`, the *stored* value of this column is no longer part of the canonical encoding at all — see Section 3.3.1 and Section 9. |
| `tombstone` | INTEGER | No, default 0 | `1` means this event's original payload has been erased under a right-to-erasure or equivalent data-minimization action. See Section 9 for the full semantics; the short version is that a tombstoned event's canonical encoding always uses the fixed `TombstoneSentinel` constant in place of whatever is or is not in the `payload` column. |
| `legal_hold` | INTEGER | No, default 0 | Per-event legal hold. `1` means this specific event is exempt from pruning regardless of age, independent of the stream-level `legal_hold` flag on the `streams` table. Only meaningful (and only ever hashed) for v2-encoded events — see Section 3.3.2. |
| `leaf_hash` | BLOB | No | 32 bytes. `SHA256([LeafPrefix] \|\| canonical_encoding(event))`, computed once against the row's canonical state and never recomputed by `verify` or `compact` — both subcommands only ever *read* this column and compare it against a freshly recomputed value; neither ever writes it. See Section 3.3.3 for the one process that is allowed to write it, and when. |

#### 3.3.1 `payload` versus canonical encoding after tombstoning

The `payload` BLOB column and "the payload bytes that get hashed" are two different things once `tombstone = 1`. Operationally, an erasure action clears the real payload from the `payload` column (that is the entire point — the sensitive bytes must actually leave storage, not just be flagged as sensitive), but the *canonical encoding* of a tombstoned event never reads the `payload` column's current contents at all; it substitutes the fixed 32-byte `TombstoneSentinel` value unconditionally. Section 9 covers why in depth. The practical consequence for anyone querying the table directly: do not infer anything about a tombstoned event's original payload from what happens to be sitting in the `payload` column after erasure (it may be `NULL`, it may be zero-length, it may in principle be left populated by an older or non-compliant erasure implementation — none of that affects hashing, and none of it should be relied upon), and do not write code that hashes `events.payload` directly without first checking `tombstone`.

#### 3.3.2 `legal_hold` and encoding version

The `events.legal_hold` column exists and is meaningful regardless of whether the owning stream has migrated to v2, but it is only ever *hashed* — included in the canonical encoding bytes that produce `leaf_hash` — for events encoded as v2. A v1-encoded event's canonical encoding has no `legal_hold` byte at all (Section 4.1); this means a v1 event's `legal_hold` flag, while it is fully honored by `compact`'s retention logic (Section 10), is not itself tamper-evident for that specific event — flipping `events.legal_hold` on a v1-encoded row without also touching anything else would not change that row's `leaf_hash` and so would not be caught by `verify`'s content check. This gap is exactly why v2 exists; see Section 11 for the full history. It is not a defect in this document's description of v1 — v1 genuinely does not hash `legal_hold` — it is a property of the legacy encoding that the v2 migration was specifically designed to close for newly-ingested and re-encoded events going forward.

#### 3.3.3 Who writes `leaf_hash`

Exactly two processes ever write `events.leaf_hash`, and both are outside ChainAudit's own two subcommands:

1. **Ingestion.** When the audit-ingest pipeline appends a new event row, it computes `leaf_hash` once, against the row's initial canonical state (untombstoned, whatever `legal_hold` value it starts with), and stores it alongside the row in the same transaction.
2. **The erasure path.** When a right-to-erasure (or equivalent) action is carried out against an already-ingested event, the process performing that erasure — part of the compliance team's data-subject-request tooling, not part of the ChainAudit CLI — atomically, in one transaction: clears the `payload` column, sets `tombstone = 1`, and **recomputes and overwrites `leaf_hash`** using the canonical encoding that substitutes `TombstoneSentinel` for the payload. This is the one and only time `leaf_hash` is ever rewritten for a row that already had one.

After either of these two write points, `leaf_hash` is permanently fixed for that row: there is no third process, no "re-ingest," and no administrative override that touches it again. `verify` and `compact` never write to this column under any circumstance. This is what "computed once at ingestion time, never recomputed in place" in the schema comment means precisely: never recomputed *in place by ChainAudit*, and never recomputed *more than once* by anything — an event's canonical state changes at most one time after ingestion (the single one-way transition from present-payload to tombstoned), and `leaf_hash` is refreshed exactly in step with that one allowed transition, by the same process that performs it, and by no one else. The practical consequence is the one described in Section 9: because storage always keeps `leaf_hash` consistent with the row's *current* canonical encoding, `verify`'s content check needs no special case for tombstoned rows at all — it recomputes the canonical encoding from current column values (which, for a tombstoned row, means using the sentinel per the tombstone rule) and compares against stored `leaf_hash`, and for any row that hasn't been tampered with outside these two sanctioned write paths, they match.

### 3.4 The `checkpoints` table

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `stream_id` | TEXT | No (PK part, FK) | References `streams.stream_id`. |
| `batch_index` | INTEGER | No (PK part) | 0-indexed, one per full batch of `checkpoint_interval` events, assigned in strictly ascending, contiguous order per stream: a stream's checkpoints are `batch_index` `0, 1, 2, …, checkpoint_count - 1` with no gaps. This contiguity is an invariant the ingest pipeline maintains and that `verify`'s structural checks assume; see Section 3.5.4. |
| `start_seq` | INTEGER | No | The `seq` of the first event in this batch, inclusive. |
| `end_seq` | INTEGER | No | The `seq` of the last event in this batch, inclusive. By construction, `end_seq - start_seq + 1 == checkpoint_interval` for the stream's current interval (Section 3.5.3), and batches are contiguous and non-overlapping: batch `i`'s `end_seq + 1` equals batch `i+1`'s `start_seq`. |
| `merkle_root` | BLOB | No | 32 bytes. The RFC 6962-style Merkle tree root (Section 5) folded over the `leaf_hash` values of every event in `[start_seq, end_seq]`, computed at checkpoint-creation time. |
| `signature` | BLOB | No | HMAC-SHA256 over `CheckpointSigningBytes(...)` (Section 7), using the key identified by `key_id`. 32 bytes. |
| `key_id` | TEXT | No | Identifies which Key Management key was used to produce `signature`. Opaque string, resolved via the KMS HTTP contract in Section 8. |
| `created_at` | INTEGER | No | Unix seconds; when this checkpoint was cut. Informational — not an input to any hash or eligibility check in this document. |

Checkpoint rows are, from ChainAudit's point of view, permanent. Neither `verify` nor `compact` ever inserts, updates, or deletes a `checkpoints` row. This means `checkpoint_count` for a stream (the number of rows in `checkpoints` for that `stream_id`) is invariant across any number of `compact` runs — pruning removes `events` rows, never `checkpoints` rows. Contrast this deliberately with `event_count`, which is exactly the number of `events` rows currently present and does shrink as batches are pruned; see Section 13.1 for how both fields show up in the `verify` report, and note carefully that a shrinking `event_count` alongside a constant `checkpoint_count` is the normal, expected signature of successful pruning, not evidence of anything wrong.

### 3.5 Invariants ChainAudit assumes but SQLite does not enforce

SQLite's `REFERENCES` clauses in the schema above are *declared* foreign keys, but SQLite does not enforce foreign key constraints unless `PRAGMA foreign_keys = ON` is set for the connection, and ChainAudit does not rely on that pragma being set by whatever process created the database. The following invariants are relied upon by the logic in this document, are normally maintained by the ingest pipeline, and are worth stating explicitly precisely because nothing in the SQLite schema itself guarantees them:

#### 3.5.1 Every `events.stream_id` has a corresponding `streams` row

`verify` and `compact` both iterate streams by reading the `streams` table and joining outward to `events` and `checkpoints`, not the other way around. An `events` row whose `stream_id` does not appear in `streams` would be invisible to both subcommands — it would not be verified, and it would not be eligible for pruning, because neither subcommand ever discovers a stream by scanning `events`. This is a deliberate consequence of the iteration order (Section 12.3), not an oversight; if a `streams` row is missing, that is an ingest pipeline bug to fix upstream, not something ChainAudit attempts to route around by inferring a stream's existence from its events.

#### 3.5.2 `events.seq` is dense and monotonic per stream

For a stream that has never been pruned, the set of `seq` values present is exactly `{0, 1, 2, ..., N-1}` for `N` total events ever ingested. After pruning, some prefix ranges of `seq` may be entirely absent (whole pruned batches), but no `seq` is ever skipped *within* a still-present range, and no `seq` is ever reused. `verify`'s content check (Section 4, Section 13.1) walks whatever `seq` values are currently present in ascending order per stream; it does not assume a particular starting point, because after pruning the lowest surviving `seq` for a stream may well be greater than zero.

#### 3.5.3 Every checkpoint's span matches its stream's `checkpoint_interval`

`end_seq - start_seq + 1` for every checkpoint row must equal the owning stream's `checkpoint_interval`. `verify` checks this as part of its structural validation (Section 4 of the JSON schema appendix documents `tampered_merkle_root` as the reason code covering this case); a checkpoint whose span does not match the stream's interval cannot correspond to a legitimately-cut batch under the interval currently on record for that stream, and is treated as a structural anomaly rather than silently trusted or silently skipped.

#### 3.5.4 `checkpoints.batch_index` is contiguous per stream

A stream's checkpoints, ordered by `batch_index`, must be exactly `0, 1, 2, ..., checkpoint_count - 1` with no gaps and no duplicates (the `PRIMARY KEY (stream_id, batch_index)` constraint already rules out duplicates at the schema level; contiguity is not separately enforced by SQLite). This matters specifically because the tip-chain fold (Section 6.3) is defined recursively over checkpoints in ascending `batch_index` order, each step depending on the previous step's output — a gap would leave "what is tip chain step 2 folded against" undefined. In practice this invariant is maintained by the ingest pipeline, which only ever cuts the next checkpoint in sequence; ChainAudit does not itself create checkpoints and so cannot itself introduce a gap, but its structural checks still confirm contiguity rather than assuming it, precisely because "assumed but unchecked" is how invariants silently rot.

#### 3.5.5 A checkpointed batch's events are all-or-nothing present

For any checkpoint with span `[start_seq, end_seq]`, the number of `events` rows currently present with `seq` in that range is either exactly `end_seq - start_seq + 1` (the batch is fully intact) or exactly `0` (the batch has been fully pruned). Any other count — some but not all of the batch's rows present — cannot result from a correctly operating `compact` (which only ever deletes a batch's entire span in one transaction, Section 10.5) and is treated by `verify` as a structural anomaly if encountered; see Section 5.5 and Section 10.6 for the precise handling.

### 3.6 Row lifecycle summary

| Row type | Created by | Mutated by | Deleted by |
|---|---|---|---|
| `streams` row | Ingest pipeline (stream provisioning) | Ingest pipeline only (e.g., setting `legal_hold`); never by `verify` or `compact` | Never, by anything in ChainAudit's scope |
| `events` row (payload intact) | Ingest pipeline, at event append time | The erasure path only, exactly once, transitioning to tombstoned | `compact`, as part of a whole-batch prune, once the batch is eligible |
| `events` row (tombstoned) | Transition from an intact row via the erasure path | Never again | `compact`, same as above — tombstoning does not exempt a batch from later eligibility on its own |
| `checkpoints` row | Ingest pipeline, when a full batch is cut | Never | Never, by anything in ChainAudit's scope |

Nothing in this table is enforced by a database trigger; it is enforced by convention across the systems that touch this schema, and this document is the record of that convention. `verify` and `compact` are both written to assume it holds and to report loudly (via the structural anomaly handling in Sections 3.5.3–3.5.5) when it appears not to.

### 3.7 Why three tables, and not fewer

It's worth justifying the schema's shape explicitly, since a flatter design is at least conceivable — one could imagine, for instance, folding `checkpoints` into `events` as a special row type, or folding per-stream configuration directly onto every event row instead of normalizing it into `streams`. Three separate tables, each with a distinct lifecycle (Section 3.6), reflects three genuinely different rates and reasons for change:

`streams` rows change rarely, and only through a small, deliberate set of operations (provisioning, migration, whole-stream legal hold toggling) — the table is small relative to the other two and is read in full on every `verify` or `compact` run (Section 12.1, Section 12.2) specifically because it's cheap to do so and because every other decision in the system starts from a stream's configuration. `events` rows are by far the highest-volume and highest-churn table — appended constantly by ingestion, and the only table `compact` ever deletes from — and keeping stream-level configuration off of every event row (rather than denormalizing `checkpoint_interval` or `retention_days` onto each one) means changing what would be stream-level configuration never requires touching potentially millions of existing rows, only the single corresponding `streams` row. `checkpoints` rows sit in between: created at a moderate, `checkpoint_interval`-governed cadence, never mutated, and — critically — never deleted even when the `events` rows they summarize are, which is precisely why they need to be a separate table from `events` rather than a row type within it: an `events`-row-that-is-secretly-a-checkpoint design would either need special handling to survive the pruning that deletes ordinary event rows, or would need pruning logic to special-case skipping it, either of which reintroduces exactly the kind of implicit, easy-to-get-wrong distinction that Section 2.6's narrow, single-table mutation surface for `compact` is designed to avoid. Three tables, three lifecycles, and a mutation surface for `compact` that can be described in one sentence (Section 2.6) are the same design decision viewed from three different angles.

## 4. Canonical Encoding Specification

### 4.1 Domain separation prefixes

Every hash computed anywhere in ChainAudit begins with a single fixed prefix byte identifying *what kind of thing* is being hashed:

```
LeafPrefix    = 0x00   // RFC 6962-style leaf hash
NodePrefix    = 0x01   // RFC 6962-style internal node hash
GenesisPrefix = 0x02   // per-stream genesis seed
TipPrefix     = 0x03   // checkpoint tip-chain fold
```

These four bytes exist for exactly one reason: so that a hash computed for one purpose can never collide in *meaning* with a hash computed for a different purpose, even in the (cryptographically remote, but not therefore irrelevant) case where the remaining bytes happen to coincide. Without domain separation, a 32-byte value floating around this system is ambiguous — is it a leaf hash, an internal Merkle node, a genesis seed, a tip-chain link? An implementation that doesn't structurally distinguish these could be tricked into accepting a value computed for one purpose as valid input for another, which is precisely the class of bug that has broken naively-designed Merkle structures elsewhere in the industry (a leaf that happens to equal some internal node's hash being replayed as if it were that node, for instance). By fixing a distinguishing first byte for every hash purpose in the system, ChainAudit makes that entire bug class structurally unreachable: a genesis seed can never be mistaken for an internal node, because the very first byte hashed into it is `0x02`, never `0x01`, and no other construction in this system ever produces a value starting from a `0x02`-prefixed preimage. This was not the original design — see the 2024-03-11 changelog entry for the incident that led to prefixes being added.

The four prefixes partition the hash space by construction *purpose*, not by *value* — nothing stops a `LeafHash` output and a `Genesis` output from coincidentally being equal 32-byte strings (SHA-256 gives no guarantee against that, nor does anything need to), but it does guarantee that no adversary can *choose* input bytes to any one of these four constructions and produce a value that will be accepted somewhere a *different* one of the four is expected, because the preimages themselves are, by construction, drawn from disjoint byte-string spaces (every `LeafHash` preimage starts with `0x00`; every `Genesis` preimage starts with `0x02`; and so on) and SHA-256 preimage resistance means you cannot go the other direction — you cannot find an input starting with `0x02` that also happens to be a valid-looking `0x00`-prefixed preimage for some other leaf, because you'd first have to find *any* preimage at all for a fixed hash output, which is exactly what SHA-256 is designed to make infeasible.

### 4.2 Encoding version is a property of the event, not the stream

Every event's canonical encoding uses one of two versions, `0x01` ("v1") or `0x02` ("v2"). Which version applies to a given event is determined by a single per-event comparison, evaluated fresh every time the encoding is needed — it is never cached on the row, never decided once for an entire stream, and never inferred from anything other than these two facts:

```
version = 0x02  if  stream.migrated_at IS NOT NULL  AND  event.ts >= stream.migrated_at
version = 0x01  otherwise
```

Read that "otherwise" carefully: it covers two distinct situations that both resolve to v1. A stream whose `migrated_at` is `NULL` has never migrated — every event in it, ingested at any point in its history, past or future, is v1. A stream whose `migrated_at` is *not* `NULL` has migrated, but that only changes the verdict for events whose own `ts` is at or after the migration point; any event in that same stream with an earlier `ts` remains v1, forever, regardless of how long ago it was ingested relative to *now* or relative to the migration event. The comparison is `event.ts >= stream.migrated_at`, so an event whose timestamp exactly equals the migration instant is v2, not v1 — the boundary is inclusive on the v2 side.

This has a consequence worth stating as plainly as possible, because it is the single most common point of confusion for anyone new to this system: **a single stream can contain both v1 and v2 events side by side, once it has migrated, indefinitely** — there is no backfill step that retroactively re-encodes old events as v2 (doing so would change their `leaf_hash`, which would break every checkpoint that already covers them). And because checkpoint batches are simply contiguous ranges of `seq`, **a single checkpoint batch can straddle the migration boundary**, containing some v1 events (those ingested, or more precisely those *timestamped*, before `migrated_at`) and some v2 events (those timestamped at or after it) in the same batch, covered by the same Merkle root. The Merkle tree construction itself (Section 5) does not care about this at all — it folds whatever 32-byte `leaf_hash` values are present for the batch's `seq` range, and a `leaf_hash` is a `leaf_hash` regardless of which encoding version produced it. Version-mixing within a batch is not an edge case to be specially handled by the tree construction; it is invisible to it by design, because the version-dependent work all happens one layer down, at the point each individual event's `leaf_hash` was computed.

Section 6.1 of the worked example below shows exactly this: a four-event checkpoint batch with two v1 events and two v2 events, folded into one Merkle root using the ordinary algorithm, no special-casing required.

### 4.3 Byte layout

The canonical encoding of an event is the following sequence of fields, concatenated with no separators, no padding, and no length prefix on the overall structure (its total length is implicit in the sum of its parts, and is never itself stored or hashed as a separate field):

| Field | Size | Encoding |
|---|---|---|
| `version` | 1 byte | `0x01` or `0x02` |
| `stream_id_len` | 2 bytes | big-endian `uint16` |
| `stream_id` | `stream_id_len` bytes | UTF-8 |
| `seq` | 8 bytes | big-endian `uint64` |
| `ts` | 8 bytes | big-endian `int64` (unix seconds), reinterpreted as a `uint64` bit pattern |
| `event_type_len` | 2 bytes | big-endian `uint16` |
| `event_type` | `event_type_len` bytes | UTF-8 |
| `payload_marker` | 1 byte | `0x00` = normal, `0x01` = tombstone |
| `payload_len` | 4 bytes | big-endian `uint32` |
| `payload_bytes` | `payload_len` bytes | raw bytes; see the tombstone rule in Section 4.5 and Section 9 |
| `legal_hold` | 1 byte | **only present when `version == 0x02`.** Absent entirely — not a zero byte, not an empty-but-present field, genuinely not there — for v1. `0x01` or `0x00` when present. |

Two consequences of this layout are easy to get wrong and worth calling out explicitly before the worked examples:

- **The `legal_hold` byte's absence in v1 is a length difference, not a value difference.** A v1 encoding of an event is strictly shorter than the v2 encoding of an otherwise-identical event by exactly one byte. Do not "pad" a v1 encoding with a synthetic zero `legal_hold` byte for uniformity, and do not default it to zero and append it regardless of version "to keep the struct simple" — doing so silently changes every v1 event's `leaf_hash` relative to what was stored at ingestion, and every v1-encoded event in the system would fail its content check the moment such a change shipped.
- **`stream_id_len` and `event_type_len` measure encoded UTF-8 bytes, not characters.** For any `stream_id` or `event_type` containing only ASCII characters these are the same number, which is most of the time in practice — but they are not the same thing in general, and an implementation that measures rune count instead of byte count will compute the wrong length prefix, and therefore the wrong bytes, and therefore the wrong hash, for any non-ASCII identifier. See Section 3.2.1.

### 4.4 Leaf hash construction

```
LeafHash(event) = SHA256( [LeafPrefix] || canonical_encoding(event) )
```

That is: prepend the single byte `0x00` to the full canonical encoding described above, and take the SHA-256 of the result. This is the value stored in `events.leaf_hash` at ingestion (or, for a tombstoned row, recomputed once at the moment of erasure — Section 3.3.3), and it is the value `verify`'s content check recomputes fresh from each row's current column state and compares against what is stored.

### 4.5 Worked example: a v1 event

Consider an event ingested into a stream `example-stream-001` before that stream had migrated to v2: `seq = 0`, `ts` = `2024-05-15T00:00:00Z` (unix `1715731200`), `event_type = "user.login"`, `payload = {"user_id":"u_4471"}` (20 bytes), not tombstoned, `legal_hold = 0`. Because this event's `ts` is prior to the stream's eventual migration point (established below as `2024-06-01T00:00:00Z`), it encodes as v1.

| Offset | Field | Length | Hex |
|---|---|---|---|
| 0 | `version` | 1 | `01` |
| 1–2 | `stream_id_len` | 2 | `0012` (18) |
| 3–20 | `stream_id` | 18 | `6578616d706c652d73747265616d2d303031` (`"example-stream-001"`) |
| 21–28 | `seq` | 8 | `0000000000000000` (0) |
| 29–36 | `ts` | 8 | `000000006643fb00` (1715731200) |
| 37–38 | `event_type_len` | 2 | `000a` (10) |
| 39–48 | `event_type` | 10 | `757365722e6c6f67696e` (`"user.login"`) |
| 49 | `payload_marker` | 1 | `00` (normal) |
| 50–53 | `payload_len` | 4 | `00000014` (20) |
| 54–73 | `payload_bytes` | 20 | `7b22757365725f6964223a22755f34343731227d` (`{"user_id":"u_4471"}`) |

Total encoded length: **74 bytes** (no `legal_hold` byte — this is v1). Concatenated:

```
0100126578616d706c652d73747265616d2d3030310000000000000000000000006643fb00000a757365722e6c6f67696e00000000147b22757365725f6964223a22755f34343731227d
```

```
LeafHash = SHA256(0x00 || <the 74 bytes above>)
         = b492bc447c14672d159140ebe875702eafafc898f6975d5bae10e90b0810e738
```

### 4.6 Worked example: a v2 event, side by side with v1

Now consider a second event, same stream, same `event_type`, structurally parallel to the one above but ingested *after* migration: `seq = 2`, `ts` = `2024-06-10T12:00:00Z` (unix `1718020800`, which is after the stream's `migrated_at` of `1717200000` / `2024-06-01T00:00:00Z`), `event_type = "user.login"`, `payload = {"user_id":"u_9002"}` (20 bytes), not tombstoned, `legal_hold = 0`. Because `ts >= migrated_at`, this encodes as v2.

| Offset | Field | Length | Hex |
|---|---|---|---|
| 0 | `version` | 1 | `02` |
| 1–2 | `stream_id_len` | 2 | `0012` (18) |
| 3–20 | `stream_id` | 18 | `6578616d706c652d73747265616d2d303031` |
| 21–28 | `seq` | 8 | `0000000000000002` (2) |
| 29–36 | `ts` | 8 | `000000006666eac0` (1718020800) |
| 37–38 | `event_type_len` | 2 | `000a` (10) |
| 39–48 | `event_type` | 10 | `757365722e6c6f67696e` |
| 49 | `payload_marker` | 1 | `00` |
| 50–53 | `payload_len` | 4 | `00000014` (20) |
| 54–73 | `payload_bytes` | 20 | `7b22757365725f6964223a22755f39303032227d` (`{"user_id":"u_9002"}`) |
| **74** | **`legal_hold`** | **1** | **`00`** |

Total encoded length: **75 bytes** — one longer than the v1 example, purely because of the trailing `legal_hold` byte. Concatenated:

```
0200126578616d706c652d73747265616d2d3030310000000000000002000000006666eac0000a757365722e6c6f67696e00000000147b22757365725f6964223a22755f39303032227d00
```

```
LeafHash = SHA256(0x00 || <the 75 bytes above>)
         = f38b8c8449c8db9cd04fed430c25fbd80540b4e19b6d8145cd1cd5461e11de35
```

Notice that the first 49 bytes of the v1 and v2 examples above are structurally identical in *shape* (version byte, then the same-length `stream_id` fields) but differ in *content* from byte 21 onward (different `seq`, different `ts`, different payload bytes) because these are two different events, not the same event encoded two ways. The point of showing them side by side is the *shape* difference — one byte of version tag at the very front, and one extra byte of `legal_hold` at the very back for v2 — not that they represent the same underlying event. Two genuinely identical events (same `stream_id`, `seq`, `ts`, `event_type`, `payload`, and `legal_hold`) encoded once as v1 and once as v2 would differ in exactly those two places and be otherwise byte-identical; but no real event is ever encoded both ways, since version is a deterministic function of `ts` and `migrated_at`, not a free choice.

### 4.7 Worked example: a tombstoned event, and why it doesn't collide with a naturally empty payload

Now consider a third event in the same stream, also post-migration (v2): `seq = 6`, `ts` = `2024-06-25T00:00:00Z` (unix `1719273600`), `event_type = "user.delete_request"`, and `tombstone = 1` — this event's payload has been erased under the right-to-erasure path (Section 9). Per the tombstone rule, the payload field of the canonical encoding is **not** whatever is or isn't currently in the `payload` column; it is always the fixed 32-byte sentinel:

```
TombstoneSentinel = SHA256("CHAINAUDIT-TOMBSTONE-SENTINEL-v1")
                   = 32d3bbf3adec96389385454fce1451dd2bd7ca45ee947d4fcd012d543cc78d1f
```

and `payload_len` for a tombstoned event is therefore always `32`, and `payload_marker` is `0x01`.

| Offset | Field | Length | Hex |
|---|---|---|---|
| 0 | `version` | 1 | `02` |
| 1–2 | `stream_id_len` | 2 | `0012` (18) |
| 3–20 | `stream_id` | 18 | `6578616d706c652d73747265616d2d303031` |
| 21–28 | `seq` | 8 | `0000000000000006` (6) |
| 29–36 | `ts` | 8 | `00000000667a0880` (1719273600) |
| 37–38 | `event_type_len` | 2 | `0013` (19) |
| 39–57 | `event_type` | 19 | `757365722e64656c6574655f72657175657374` (`"user.delete_request"`) |
| **58** | **`payload_marker`** | **1** | **`01`** (tombstone) |
| **59–62** | **`payload_len`** | **4** | **`00000020`** (32, not 0) |
| **63–94** | **`payload_bytes`** | **32** | **`32d3bbf3adec96389385454fce1451dd2bd7ca45ee947d4fcd012d543cc78d1f`** (the sentinel, not the erased original payload) |
| 95 | `legal_hold` | 1 | `00` |

Total encoded length: **96 bytes**. Concatenated:

```
0200126578616d706c652d73747265616d2d303031000000000000000600000000667a08800013757365722e64656c6574655f72657175657374010000002032d3bbf3adec96389385454fce1451dd2bd7ca45ee947d4fcd012d543cc78d1f00
```

```
LeafHash = SHA256(0x00 || <the 96 bytes above>)
         = 913eb1a2a75e8032c29ed72e97914564a7de4de575eebcdb4f87807306beb3e4
```

Now contrast this with a *different* event in the same stream that legitimately never had a payload at all — a heartbeat with no application-level content — `seq = 8`, `ts` = `2024-06-27T00:00:00Z` (unix `1719446400`), `event_type = "system.heartbeat"`, `payload_marker = 0x00`, `payload_len = 0`, zero payload bytes:

```
0200126578616d706c652d73747265616d2d303031000000000000000800000000667cab80001073797374656d2e686561727462656174000000000000
```

```
LeafHash = cf28c1aed405a49e361d912868535da102fbfef187413908ca1b426f6046372b
```

These two encodings — the tombstoned event and the naturally-empty-payload event — are unrelated 61-byte-vs-96-byte strings producing unrelated hashes, and that is exactly the property the sentinel exists to guarantee. Before this design, an early implementation handled erasure by simply clearing `payload` to a zero-length value and leaving `payload_marker = 0x00` unchanged (Section 16, 2024-04-29 and 2024-05-06 entries) — which meant an erased event's canonical encoding became bit-for-bit indistinguishable in shape from a legitimately-always-empty event's encoding *except* for the fields (`seq`, `ts`, `event_type`) that were going to differ anyway because they're different events. The actual defect this caused was not a hash collision in the cryptographic sense — different `seq`/`ts`/`event_type` values mean different hashes regardless — but an *auditability* collision: nothing in the stored bytes, and therefore nothing in the hash, recorded the fact that an erasure had occurred at all. A compliance reviewer inspecting the raw encoding of a row could not distinguish "this event never had a payload" from "this event's payload was removed," which defeated the actual purpose of tracking erasure as a distinct, provable event in the audit trail — the entire reason the `tombstone` column and this sentinel mechanism exist is so that *erasure itself* is a tamper-evident, auditable fact, not merely an operation that happens to leave a shorter row behind. Making `payload_marker`, `payload_len`, and `payload_bytes` all diverge sharply and unconditionally between the two cases (`0x00`/`0`/empty versus `0x01`/`32`/sentinel) makes that distinction explicit and hashed, not incidental and unhashed.

The second property the sentinel buys, mentioned in Section 3.3.3 above and worth restating here at the byte level: because the row's `leaf_hash` is recomputed (once, atomically, by the erasure path) against this sentinel-substituted encoding at the moment erasure happens, `verify`'s later recomputation — which always uses current column state, including current `tombstone` — reproduces the same sentinel-substituted bytes and therefore the same hash. Legitimate erasure never causes a content-check mismatch. A content-check mismatch on a tombstoned row still means exactly what it means on any other row: something changed this row's stored fields (or its stored `leaf_hash`) outside of the two sanctioned write paths in Section 3.3.3.

### 4.8 Worked example: a legal-hold event

Finally, an event with `legal_hold = 1` set — `seq = 7`, `ts` = `2024-06-26T00:00:00Z` (unix `1719360000`), `event_type = "user.login"`, `payload = {"user_id":"u_9002"}`, not tombstoned, v2 (post-migration):

```
0200126578616d706c652d73747265616d2d303031000000000000000700000000667b5a00000a757365722e6c6f67696e00000000147b22757365725f6964223a22755f39303032227d01
```

The only difference from the v2 worked example in Section 4.6 above is the final byte: `01` instead of `00`. That single trailing bit is the entirety of what makes an event's legal-hold status tamper-evident under v2 — flip it in the database without going through a sanctioned write path, and the freshly recomputed `LeafHash` no longer matches the stored one:

```
LeafHash = 5f496470b82b0f826be880c39df2c54781b7af7f8556ee71d8196a95ff936ae0
```

Compare against Section 4.6's `f38b8c8449c8db9cd04fed430c25fbd80540b4e19b6d8145cd1cd5461e11de35` for the otherwise-identical `legal_hold = 0` case (different `seq`/`ts` as well, since these are two distinct real events in the running example, not the same event toggled — but the mechanism is the same one that would catch an in-place toggle of a single row: any change to any hashed field, including this one trailing byte, produces an unrelated 32-byte output, by design of SHA-256).

### 4.9 Illustration: what tampering actually looks like at the hash level

To make concrete what "content check fails" means operationally, take the v2 event from Section 4.6 (`seq = 2`, original payload `{"user_id":"u_9002"}`) and suppose someone edits the stored `payload` BLOB directly in the database to read `{"user_id":"u_9099"}` instead — an eight-character change, one digit of one field — without going through ingestion or the erasure path, and, critically, without updating `leaf_hash` to match (an attacker capable of quietly editing `payload` but not `leaf_hash` is exactly the threat model this system defends against; an attacker capable of consistently updating both would need to compromise the ingestion path's or erasure path's write access, which is a different and larger problem outside ChainAudit's scope to detect on its own).

```
original payload_bytes: 7b22757365725f6964223a22755f39303032227d   ({"user_id":"u_9002"})
tampered payload_bytes: 7b22757365725f6964223a22755f39303939227d   ({"user_id":"u_9099"})

original LeafHash = f38b8c8449c8db9cd04fed430c25fbd80540b4e19b6d8145cd1cd5461e11de35
tampered LeafHash = ac306cab4ba056ae32e380567696e3c1e68dfd5d7dcf4960c0dd502e00dbc000
```

The freshly recomputed hash (`ac306c...`) no longer matches the stored `leaf_hash` column (which still holds `f38b8c...`, since nothing in this scenario touched that column). `verify`'s content check catches this at `seq = 2` — this is precisely what populates `first_bad_seq` and yields `reason = "tampered_event"` (Section 13.1). Note that this is a two-bit-different payload producing a completely unrelated 32-byte digest, with no partial similarity between the two hashes — this is the avalanche property of SHA-256 doing exactly what it's supposed to do, and it is why even a single-character edit anywhere in a hashed field is unconditionally detectable, not just large or obviously suspicious edits.

### 4.10 Encoding shapes at a glance

Sections 4.5 through 4.8 work through five worked examples in full byte-level detail. Collected here as a single quick-reference table, all drawn from the same `example-stream-001` running scenario, so the shape differences are easy to compare side by side without re-deriving each one:

| Example | Section | version | payload_marker | payload_len | trailing `legal_hold`? | Total length | LeafHash (first 16 hex chars, for quick visual distinction) |
|---|---|---|---|---|---|---|---|
| v1 event, real payload | 4.5 | `0x01` | `0x00` | 20 | absent | 74 bytes | `b492bc447c14672d...` |
| v2 event, real payload, `legal_hold=0` | 4.6 | `0x02` | `0x00` | 20 | `0x00` | 75 bytes | `f38b8c8449c8db9c...` |
| v2 event, tombstoned | 4.7 | `0x02` | `0x01` | 32 | `0x00` | 96 bytes | `913eb1a2a75e8032...` |
| v2 event, naturally empty payload | 4.7 | `0x02` | `0x00` | 0 | `0x00` | 61 bytes | `cf28c1aed405a49e...` |
| v2 event, real payload, `legal_hold=1` | 4.8 | `0x02` | `0x00` | 20 | `0x01` | 75 bytes | `5f496470b82b0f82...` |

Two things worth noticing from the table as a whole rather than from any one row: first, every version/marker/legal_hold combination produces a structurally distinct byte layout (different length, in every case except the two `legal_hold` variants which are — correctly — identical in length and differ only in their final byte, Section 4.8); second, none of the five leading 16-hex-character prefixes share so much as their first byte, which is exactly the avalanche behavior Section 4.9 discusses, here visible across encodings that are structurally close to each other rather than only across a single deliberately-tampered field.

### 4.11 Encoding edge cases

| Case | Behavior |
|---|---|
| `stream_id` or `event_type` containing non-ASCII UTF-8 | Length prefix is the UTF-8 **byte** length, not the rune count. A four-byte emoji contributes 4 to `stream_id_len`, not 1. |
| `stream_id` longer than 65,535 UTF-8 bytes | Cannot be represented — `stream_id_len` is a `uint16`. Not expected to occur in practice; the ingest pipeline enforces a much smaller practical limit upstream. |
| `event_type` longer than 65,535 UTF-8 bytes | Same constraint as above, same practical non-occurrence. |
| `payload` larger than 4 GiB (2^32 − 1 bytes) | Cannot be represented — `payload_len` is a `uint32`. ChainAudit itself enforces no smaller limit; realistic payload sizes for audit-log entries are many orders of magnitude below this, and any smaller cap is an ingestion-side policy, not a wire-format constraint. |
| `payload` is SQL `NULL` (not zero-length, but absent) versus zero-length | Both hash identically: the canonical encoding only ever sees a byte slice of some length for `payload_bytes` (0 for either `NULL` or an empty `BLOB`), and `payload_len = 0` in both cases. ChainAudit does not distinguish SQL `NULL` payload from zero-length payload at the encoding level; if this distinction ever needs to become meaningful, it will require a new encoding version, not a reinterpretation of the existing one. |
| `ts` before the unix epoch (negative) | The 8-byte field is still the big-endian two's-complement bit pattern of the `int64` value, reinterpreted as an unsigned 64-bit integer for the purposes of byte layout only (this affects only how the bytes look, not the comparison logic elsewhere in the system, which always operates on the signed `int64` value). Not expected in practice for an audit log, but the byte layout is well-defined for it regardless. |
| `ts` far in the future (beyond `int64` seconds range) | Not representable; `int64` seconds overflows in the year 292,277,026,596, which is not considered a practical constraint. |
| Two events in the same stream with identical `ts` | Fully legal. `seq` order, not `ts` order, is authoritative for ingestion order; nothing in this document assumes `ts` values are unique or strictly increasing, only that they are non-decreasing is *not even assumed* — `ts` is producer-supplied and `seq` is what ChainAudit trusts for ordering. |
| `legal_hold` byte value other than `0x00` or `0x01` | Not producible by any sanctioned write path (the column is an `INTEGER` constrained by application logic to 0 or 1, not by a SQLite `CHECK` constraint). If encountered, treat any non-zero stored value as boolean-true for encoding purposes — but its mere presence differing from what ingestion would have written is itself the kind of thing the content check exists to catch. |

## 5. Merkle Tree Construction

### 5.1 The algorithm

ChainAudit uses the RFC 6962 Merkle Tree Hash (MTH) construction, unmodified in its recursive structure, with ChainAudit's own domain-separated node hash function substituted for RFC 6962's. Formally, for a list of leaf hashes `leaves[0:n]`:

```
MTH(leaves[0:1]) = leaves[0]                                          // already a leaf hash, n = 1
MTH(leaves[0:n]) = InternalHash(MTH(leaves[0:k]), MTH(leaves[k:n]))    for n > 1
  where k = the largest power of two strictly less than n
```

```
InternalHash(left, right) = SHA256( [NodePrefix] || left || right )
```

`k` splits the leaf range unevenly whenever `n` is not itself a power of two: the left subtree `leaves[0:k]` is always a complete (perfectly balanced) binary tree of exactly `k = 2^m` leaves, and the right subtree `leaves[k:n]` absorbs whatever is left over, recursing under the same rule. This is deliberate and is the entire content of the algorithm — there is no other rule, no padding, and no special case beyond the `n = 1` base case (a single leaf hash is its own Merkle root; a checkpoint never covers zero events, so `n = 0` never arises — see Section 5.6).

A useful way to compute `k` without a table of powers of two: start `k = 1`, and while `k * 2 < n`, double `k`. This terminates with `k` equal to the largest power of two strictly less than `n`, for any `n >= 2`.

### 5.2 Worked example: five leaves

Consider a stream `example-stream-002`, never migrated to v2 (pure v1 legacy, `migrated_at IS NULL`), with `checkpoint_interval = 5`. Its first checkpoint batch covers five events, `seq 0` through `seq 4`, a small job-tracking sequence:

| seq | ts (unix) | event_type | payload |
|---|---|---|---|
| 0 | 1710028800 | `job.started` | `{"job_id":"j-100"}` |
| 1 | 1710029100 | `job.progress` | `{"job_id":"j-100","pct":50}` |
| 2 | 1710029340 | `job.progress` | `{"job_id":"j-100","pct":100}` |
| 3 | 1710029400 | `job.completed` | `{"job_id":"j-100","status":"ok"}` |
| 4 | 1710029405 | `job.archived` | `{"job_id":"j-100"}` |

Each event's canonical encoding is v1 (this stream has never migrated), computed exactly as described in Section 4. Their leaf hashes:

```
L0 = LeafHash(seq=0) = ee53c9e206c346eba024300993de0375798ea2821db2b10191b29259f1048ae0
L1 = LeafHash(seq=1) = ee3ee6df5597e97db17d00c16301119b18becd7527df9c9e924fd547cc894482
L2 = LeafHash(seq=2) = e91e5639214666bbd9fda39aa4e66018f07fc2ffa6a1a79a3ad33c31056f8c9b
L3 = LeafHash(seq=3) = 7ec9974cfd6bace98955730edb3883442b324e0c1552804309eaf37ab0b4a182
L4 = LeafHash(seq=4) = 6378d238c4d69c8395d7429aeccee1750c3c1cbc4d95bb59a18eb68e78c5eba4
```

For `n = 5`: `k = 4` (largest power of two strictly less than 5), so `MTH(0:5) = InternalHash(MTH(0:4), MTH(4:5))`. `MTH(4:5)` is the single-leaf base case, `L4` itself. `MTH(0:4)` recurses with `n = 4`, `k = 2`: `InternalHash(MTH(0:2), MTH(2:4))`, and each of those is the ordinary two-leaf pairing (`n = 2`, `k = 1`). The resulting shape is:

```
                              root
                             /    \
                        node0123    L4
                        /      \
                  node01        node23
                  /    \        /    \
                L0      L1    L2      L3
```

Or, in the parenthesized notation used elsewhere in this document: `(((L0,L1),(L2,L3)),L4)`. Computing bottom-up:

```
node01     = InternalHash(L0, L1) = SHA256(0x01 || L0 || L1)
           = a9c673addae77dfd2077a547cc89701ccd3838697374d43fa983a445b49d8c07

node23     = InternalHash(L2, L3) = SHA256(0x01 || L2 || L3)
           = 978074fd016ed216e871aae54d0c19defff38817effff6948e3fefd8228b6a0f

node0123   = InternalHash(node01, node23) = SHA256(0x01 || node01 || node23)
           = 4bfdfc8ef938085c06e980b987861af822b5d1b1c52eedd56c06d13d544aa309

root       = InternalHash(node0123, L4) = SHA256(0x01 || node0123 || L4)
           = 439c0ee7525abdc4b24b2c60456bc12a7342053ac8b951406e1b55824a037412
```

`439c0ee7525abdc4b24b2c60456bc12a7342053ac8b951406e1b55824a037412` is the `merkle_root` stored on this stream's first checkpoint row. Notice that `L4` is folded directly into the top of the tree, paired against the root of the balanced four-leaf subtree beneath it — it is never duplicated, never paired with a copy of itself, and never held at a different tree depth than a naive "pad to the next power of two" approach would put it. It sits at depth 1 from the root (one hash away), while `L0` through `L3` sit at depth 3 (three hashes away). This asymmetry — the odd-one-out ends up *shallower* in the tree, not deeper or specially wrapped — is characteristic of RFC 6962's splitting rule and is exactly what the next two subsections contrast against alternatives that get this wrong.

### 5.3 An equivalent, iterative formulation

The recursive definition in Section 5.1 is the normative one, but it is worth recording — because it answers a question worth asking once and then never again — that an iterative, bottom-up construction produces byte-identical results: repeatedly pair adjacent leaves left to right at the current level (`InternalHash(level[0], level[1])`, `InternalHash(level[2], level[3])`, ...), and if the current level has an odd number of nodes, carry the final, unpaired node forward to the next level **unchanged** (not duplicated, not re-hashed on its own — simply promoted as-is), then repeat on the new level until exactly one node remains.

Applying this to the same five leaves above: level 0 is `[L0, L1, L2, L3, L4]` (5 nodes, odd). Pairing gives `node01` and `node23`, with `L4` left over and carried forward unchanged. Level 1 is `[node01, node23, L4]` (3 nodes, odd again). Pairing gives `node0123`, with `L4` again left over and carried forward unchanged. Level 2 is `[node0123, L4]` (2 nodes, even) — pairing gives the final root, `InternalHash(node0123, L4)`. This is the identical sequence of hash calls as the recursive derivation above, and produces the identical root, `439c0ee7...`, confirmed by direct computation, not merely by argument. Some ChainAudit-adjacent tooling (streaming checkpoint construction, where the total leaf count isn't known until the batch closes) builds the tree this iterative way rather than recursively; both are correct, and this document treats them as fully interchangeable. Do not read this equivalence as suggesting *any* odd-node-carrying rule is fine, though — Section 5.4 below is a rule that looks superficially similar and is not equivalent at all.

### 5.4 Explicitly rejected: Bitcoin-style duplicate-last-node

A different and non-equivalent construction, used by Bitcoin's transaction Merkle tree and by a number of systems that copied its approach, handles an odd node count at a given level not by carrying the lone node forward unchanged, but by **duplicating** it — appending a second copy of the same node so the level has an even count, then pairing as usual, including pairing the duplicated node with itself. **ChainAudit does not use this construction.** It is described here only to rule it out explicitly, because it is common enough elsewhere that an engineer porting logic from a different system might reach for it out of habit.

Applying duplicate-last-node to the same five leaves from Section 5.2, using the same `InternalHash` primitive (so that the comparison isolates the tree-shape rule from any hash-function difference):

```
Level 0 (5 nodes, odd): [L0, L1, L2, L3, L4]
  duplicate L4 -> [L0, L1, L2, L3, L4, L4]
  pair -> [ InternalHash(L0,L1), InternalHash(L2,L3), InternalHash(L4,L4) ]
        = [ a9c673ad...8c07, 978074fd...b6a0f, f2dd1f92258b2f58a9bd82c9626942e0d460f4dc51071673a9a1460d62f32e35 ]

Level 1 (3 nodes, odd): duplicate the last -> 4 nodes
  pair -> [ InternalHash(node01,node23), InternalHash(dup4,dup4) ]
        = [ 4bfdfc8e...aa309, b5fb3f90c00af18c123d6cef207c7419eda1363c8297cacfdb157bf9c1d82046 ]

Level 2 (2 nodes, even): pair -> root
        = InternalHash(4bfdfc8e...aa309, b5fb3f90...82046)
        = 6d11ae76658baca574d930129a3f1e96813bd505b2cd9bce68aa0fa2ce70a4c8
```

```
Bitcoin-style duplicate-last-node root (same 5 leaves) = 6d11ae76658baca574d930129a3f1e96813bd505b2cd9bce68aa0fa2ce70a4c8
RFC 6962 root, this system's actual construction        = 439c0ee7525abdc4b24b2c60456bc12a7342053ac8b951406e1b55824a037412
```

Completely different 32-byte values, from the identical five leaves and the identical underlying hash primitive — the only thing that differs is how the odd leftover at each level is handled. If `verify` or any other component of this system were to (re-)implement Merkle folding using duplicate-last-node instead of the RFC 6962 rule, it would compute `6d11ae76...` for this batch, compare it against the stored `merkle_root` of `439c0ee7...`, find a mismatch, and incorrectly report `tampered_merkle_root` for a batch that was never tampered with at all — the checkpoint's signature and every event's content check would be entirely valid, and the "corruption" would exist only in the disagreement between two different tree algorithms, not in the data. This is worth internalizing precisely because it is a *silent* failure mode: nothing about a duplicate-last-node implementation crashes, errors loudly, or looks obviously broken in testing against even-sized batches (Section 5.6 below shows why even-sized batches don't distinguish the two algorithms at all) — it only diverges once an odd count appears anywhere in the recursion, which for real checkpoint batches is any batch whose size is not itself a power of two, i.e., most batches in practice, since `checkpoint_interval` is operator-chosen and has no reason to be a power of two.

Beyond producing a different root, duplicate-last-node as historically implemented (including Bitcoin's own) also does not apply the leaf/node domain separation described in Section 4.1 — the duplicated node is hashed using the same function as every other internal node, but the *leaves themselves* are typically hashed with no distinguishing prefix from internal nodes at all in these older designs, which is a second, independent defect (the leaf/internal-node type-confusion issue) layered on top of the tree-shape difference. ChainAudit's rejection of duplicate-last-node is really a rejection of two separate bad ideas that happen to travel together in the systems that popularized this approach; Section 4.1 covers the domain-separation half, this section covers the tree-shape half, and both would need to be true simultaneously for a reimplementation to accidentally match ChainAudit's actual construction, which is precisely why "clone a Merkle tree implementation from a blockchain codebase" is not a shortcut that works here.

### 5.5 Why even-sized batches don't reveal the difference

It's worth being explicit about why this divergence is easy to miss in casual testing: for any `n` that is itself a power of two, every level of the recursion has an even count, no odd-leftover rule (RFC 6962's "carry unchanged," or duplicate-last-node's "duplicate") is ever invoked, and every reasonable Merkle construction — RFC 6962, duplicate-last-node, and the iterative pair-and-carry formulation — produces the identical, unambiguous, perfectly-balanced binary tree. A `checkpoint_interval` of 4, 8, 16, 32, or any other power of two will never exercise the odd-count branch of any of these algorithms, and a reimplementation with the wrong odd-count rule will pass every test run against such a stream and only diverge the day it encounters a stream configured with a non-power-of-two `checkpoint_interval` — which, again, is the common case, since there is no requirement anywhere in this system that `checkpoint_interval` be a power of two, and most operator-chosen values (50, 100, 500, 1,000) are not.

### 5.6 Applying the algorithm to a batch straddling the v1 → v2 migration boundary

Merkle construction is entirely indifferent to encoding version — it operates purely on the 32-byte `leaf_hash` values already computed for each event, and never inspects, or needs to inspect, which encoding version produced any of them. To make this concrete, return to `example-stream-001` from Section 4, with `checkpoint_interval = 4` and `migrated_at = 2024-06-01T00:00:00Z` (unix `1717200000`). Its first checkpoint batch, `seq 0` through `seq 3`, straddles the migration boundary: `seq 0` and `seq 1` predate `migrated_at` and are v1-encoded; `seq 2` and `seq 3` postdate it and are v2-encoded.

```
leaf0 (seq=0, v1) = b492bc447c14672d159140ebe875702eafafc898f6975d5bae10e90b0810e738
leaf1 (seq=1, v1) = c92b44f3de197605985b406b00a50c5120b4ffe1171ababf2a920bd3a6b0cb20
leaf2 (seq=2, v2) = f38b8c8449c8db9cd04fed430c25fbd80540b4e19b6d8145cd1cd5461e11de35
leaf3 (seq=3, v2) = a3c257f98f9973f64f4d4ce753cfedb03fd5d273cbe8d15baff345e5599ed274
```

`n = 4` is a power of two, so this is the simple balanced case from Section 5.5 — `k = 2` at the top level, giving the ordinary two-and-two pairing:

```
node(leaf0,leaf1) = InternalHash(leaf0, leaf1) = 63ac4f1c0fa11713499b2c8330e580a48c09bf26db50ebf8d786623488a1449f
node(leaf2,leaf3) = InternalHash(leaf2, leaf3) = 816958285b579eb569ddbb99c41b230e862df055ed9f8f653ab311d02d76caa3
root              = InternalHash(node(leaf0,leaf1), node(leaf2,leaf3))
                  = 48fe1a4765049c3a1797790204b7375de9c7a684f4ec2d89c5e6005d867f2806
```

Nothing about this computation branches on version, checks `migrated_at`, or treats `leaf0`/`leaf1` any differently from `leaf2`/`leaf3` — by the time Merkle construction runs, version has already done its only job (determining how each leaf hash was computed in the first place, back in Section 4) and has nothing further to contribute. This is the practical demonstration of the claim in Section 4.2: a checkpoint batch mixing v1 and v2 events is not a special case the tree-construction code needs to know about; it is invisible to it by construction. `48fe1a4765049c3a1797790204b7375de9c7a684f4ec2d89c5e6005d867f2806` is this stream's first checkpoint's `merkle_root`, used again in the checkpoint-signing worked example in Section 7.2 and the tip-chain worked example in Section 6.4.

### 5.7 Edge cases

| Case | Behavior |
|---|---|
| `n = 1` (a checkpoint interval of exactly 1, unusual but not prohibited) | `MTH` of a single leaf is that leaf hash itself, with no `InternalHash` call at all. The checkpoint's `merkle_root` equals `leaf_hash` of its one event, verbatim. |
| `n = 0` | Never arises. A checkpoint by definition covers a full batch of `checkpoint_interval >= 1` events (Section 3.2); there is no such thing as a zero-event checkpoint, and `verify` never attempts to compute `MTH` of an empty leaf list. |
| A checkpoint batch whose events have all been pruned | `verify` does not attempt to recompute `merkle_root` at all in this case — there are no leaf hashes left to fold, and treating their absence as a fold-to-nothing-and-compare-to-stored-root failure would incorrectly flag every successfully compacted stream as corrupt. See Section 10.6 for the precise handling; the checkpoint's signature (Section 7) is what continues to stand in for structural proof of that batch once its rows are gone. |
| A checkpoint batch with some but not all of its rows present | Not producible by a correctly operating `compact` (pruning is strictly whole-batch, Section 10.5) and treated by `verify` as a structural anomaly — see Section 3.5.5. |
| `checkpoint_interval` is a power of two | Every level of the recursion is even; RFC 6962, the iterative pair-and-carry formulation, and (incorrectly, for this system) duplicate-last-node would all agree. This is not a reason to prefer power-of-two intervals; it only means the algorithm choice is untestable against such a stream, which is itself worth knowing (Section 5.5). |
| Two different streams' checkpoints happen to share a `merkle_root` value | Structurally irrelevant on its own — `merkle_root` is not, by itself, what gets signed; `CheckpointSigningBytes` (Section 7) binds in `stream_id` and batch coordinates specifically so a coincidental root collision between unrelated batches can never make one checkpoint's signature validate for another. |

## 6. Genesis and the Checkpoint Tip Chain

### 6.1 Genesis

Every stream has a genesis value, derived purely from its `stream_id` and nothing else:

```
Genesis(stream_id) = SHA256( [GenesisPrefix] || "CHAINAUDIT-GENESIS-v1" || stream_id )
```

`GenesisPrefix` is `0x02` (Section 4.1). `"CHAINAUDIT-GENESIS-v1"` is a fixed ASCII literal, hashed as its UTF-8 bytes, included specifically so that genesis derivation is its own distinct domain even among the already-domain-separated set of hash purposes — the version suffix (`-v1`) exists so that if genesis derivation ever needs to change in a future format revision, the new construction can use `-v2` and be unambiguously distinct from every genesis value ever computed under this one, without needing a fifth top-level prefix byte. `stream_id` is the raw UTF-8 bytes of the stream identifier, with **no length prefix** — unlike every other place `stream_id` appears in this document's hash constructions (Section 4.3, Section 7.1), genesis derivation does not prepend a `BE16(len(stream_id))` field. This is safe specifically because `stream_id` is the *last* field in the genesis preimage; there is nothing after it whose boundary could be confused by a variable-length, unprefixed `stream_id`. Contrast this with `CheckpointSigningBytes` (Section 7.1), where `stream_id` is *not* the last field, and where omitting its length prefix would make the boundary between `stream_id` and `batch_index` ambiguous — that is precisely why it is length-prefixed there and not here.

Worked example:

```
Genesis("example-stream-001") = SHA256( 0x02 || "CHAINAUDIT-GENESIS-v1" || "example-stream-001" )
                               = 454630090e99c25ad622f19bfcfd5d137a6e90f81ba7be1403db68fa0686fb78

Genesis("example-stream-002") = SHA256( 0x02 || "CHAINAUDIT-GENESIS-v1" || "example-stream-002" )
                               = 3eebc48697a551d1c4439cb58794921796d4e8051aeadc499a06d655a3c5574a
```

Genesis is computed the same way regardless of whether the stream has ever ingested a single event, ever been checkpointed, or ever migrated to v2 — it depends on nothing but the identifier string itself, and it is defined for every `stream_id` that could ever exist, not merely ones that happen to have rows in `streams` today. In practice, of course, ChainAudit only ever computes `Genesis` for streams it finds a row for, but the function itself has no such precondition.

### 6.2 The tip chain

A stream's checkpoints, folded in ascending `batch_index` order starting from genesis, form the **tip chain**:

```
tip_0 = Genesis(stream_id)                                  // before the stream has any checkpoints

tip_i = SHA256( [TipPrefix] || tip_{i-1}
                              || BE64(batch_index)
                              || BE64(start_seq)
                              || BE64(end_seq)
                              || merkle_root
                              || BE16(len(key_id)) || key_id_bytes )

chain_tip_hash(stream) = tip_N     // N = number of checkpoints; genesis itself if there are none yet
```

Each step folds in exactly the fields that identify *which batch this is* (`batch_index`, `start_seq`, `end_seq`), *what it attests to* (`merkle_root`), and *under what key it was signed* (`key_id`, itself length-prefixed since it is not the final field in this preimage) — plus the previous tip, which is what makes this a *chain*: `tip_i` cannot be computed without already knowing `tip_{i-1}`, which cannot be computed without `tip_{i-2}`, all the way back to `tip_0 = Genesis`. Reordering two checkpoints, skipping one, or substituting a different stream's checkpoint into the middle of this fold all produce a completely different `tip_N`, with no partial credit — this is the same avalanche property discussed in Section 4.9, applied here to checkpoint bookkeeping instead of event payloads.

Note what is *not* folded into `tip_i`: the checkpoint's `signature` itself, and its `created_at` timestamp. The signature is deliberately excluded because the tip chain's job is to commit to *what was checkpointed* (the batch coordinates and the root), not to *how it was attested* — signature validity is checked separately, against the Key Management service, as its own distinct verification step (Section 7, Section 8); folding the signature into the tip chain would conflate "this is the sequence of checkpoints this stream has" with "every one of those checkpoints' signatures still validates against a currently-active key," and those are exactly the two questions Section 8.3 spends considerable space keeping distinct. `created_at` is excluded because it is bookkeeping metadata with no bearing on the cryptographic content of the batch — two otherwise-identical checkpoints cut at different wall-clock times (which cannot really happen for the *same* batch, but the point is about what the construction is designed to be indifferent to) would fold identically.

### 6.3 Worked example: a two-checkpoint tip chain

Continuing the `example-stream-001` example from Sections 4 and 5: its first checkpoint (`batch_index = 0`, `start_seq = 0`, `end_seq = 3`, `merkle_root = 48fe1a47...f2806`, `key_id = "kms-2024-06-a"`) folds against genesis:

```
tip_0 = Genesis("example-stream-001") = 454630090e99c25ad622f19bfcfd5d137a6e90f81ba7be1403db68fa0686fb78

tip_1 = SHA256( 0x03 || tip_0
                     || BE64(0)                                    // batch_index
                     || BE64(0)                                    // start_seq
                     || BE64(3)                                    // end_seq
                     || 48fe1a4765049c3a1797790204b7375de9c7a684f4ec2d89c5e6005d867f2806   // merkle_root
                     || BE16(14) || "kms-2024-06-a" )               // key_id, length-prefixed
      = 447ce3ae21274f1286bc1a0a160f1addb87b9b787018c5f8c7be6d811c7d7150
```

A second checkpoint follows (`batch_index = 1`, `start_seq = 4`, `end_seq = 7`, `merkle_root = 4933572c...fa4816`, computed from the four v2 events including the tombstoned and legal-hold events from Section 4, same `key_id`):

```
tip_2 = SHA256( 0x03 || tip_1
                     || BE64(1)
                     || BE64(4)
                     || BE64(7)
                     || 4933572c4aad4fddb945232ce13a055b502c82aff1de6f0901b2ec7724fa4816
                     || BE16(14) || "kms-2024-06-a" )
      = 84e97146283735253c14119f3fe742217b445736257777b5ecae2dbc25f52acc
```

Since this stream has exactly two checkpoints, `chain_tip_hash("example-stream-001") = tip_2 = 84e97146283735253c14119f3fe742217b445736257777b5ecae2dbc25f52acc` — this is the value that would appear in the `chain_tip_hash` field of this stream's entry in both `verify_report.json` and `compact_manifest.json` (Section 13), for as long as this stream's checkpoint set doesn't change (which, per Section 3.4, it never does — checkpoints are permanent).

For comparison, `example-stream-002` (Section 5.2) has a single checkpoint (`batch_index = 0`, `start_seq = 0`, `end_seq = 4`, `merkle_root = 439c0ee7...a037412`, `key_id = "kms-2024-03-a"`):

```
tip_0 = Genesis("example-stream-002") = 3eebc48697a551d1c4439cb58794921796d4e8051aeadc499a06d655a3c5574a

tip_1 = SHA256( 0x03 || tip_0 || BE64(0) || BE64(0) || BE64(4)
                     || 439c0ee7525abdc4b24b2c60456bc12a7342053ac8b951406e1b55824a037412
                     || BE16(14) || "kms-2024-03-a" )
      = 34fd4312f16061e9e0c053e2ee251be0bd9601cb74021f61d047e9c9652c1f93
```

`chain_tip_hash("example-stream-002") = 34fd4312f16061e9e0c053e2ee251be0bd9601cb74021f61d047e9c9652c1f93`.

### 6.4 The cross-artifact invariant: `chain_tip_hash` is pruning-independent

This is the single most important property in this entire document, and it is what makes `verify` and `compact` two views onto one consistent system rather than two independent, potentially-disagreeing tools. State it precisely:

> **`chain_tip_hash` is a pure function of a stream's checkpoint chain — the sequence of `(batch_index, start_seq, end_seq, merkle_root, key_id)` tuples across its `checkpoints` rows, folded in order from genesis. It is never, under any construction in this document, a function of raw `events` rows.**

Look again at the fold formula in Section 6.2: every field folded into `tip_i` comes from the `checkpoints` table. None comes from `events`. This is not an incidental property of the specific fields chosen — it is the entire design intent, and it has a direct, load-bearing consequence for `compact`:

`compact`'s only mutation, anywhere in this system, is deleting whole batches of `events` rows once they are eligible for pruning (Section 2.6, Section 10.5). It never touches `checkpoints`. Since `chain_tip_hash` is computed exclusively from `checkpoints` data, and `checkpoints` data is invariant across any `compact` run, **pruning a stream's oldest eligible batches can never change that stream's `chain_tip_hash`** — not approximately, not usually, but as a matter of construction: the function that computes `chain_tip_hash` literally never reads the table `compact` modifies. A `verify` report generated immediately before a `compact` run, and a `compact` manifest generated by that run, and a second `verify` report generated immediately after, will all show byte-identical `chain_tip_hash` values for every stream that had any batches pruned (and, trivially, for every stream that didn't). This is exactly why `compact_manifest.json` includes a `chain_tip_hash` field per stream at all (Section 13.2) — its entire purpose is to let an operator or an automated check confirm this invariant held for a specific run, by comparing it against the corresponding `verify_report.json` value for the same stream, taken before and after.

Concretely, using the worked chain above: if `example-stream-001`'s first checkpoint batch (`seq 0`–`3`) becomes eligible for pruning and `compact` deletes those four `events` rows, `example-stream-001`'s `chain_tip_hash` remains `84e97146283735253c14119f3fe742217b445736257777b5ecae2dbc25f52acc` — the exact value computed above while all eight events (`seq 0`–`7`) were still present. Recomputing the tip chain after the deletion folds the identical `checkpoints` rows in the identical order, because deleting `events` rows never touches `checkpoints` rows. The four now-missing raw rows are not inputs to this computation and never were.

This is precisely the sense in which "pruning requires a checkpoint's signed Merkle root to stand in for the deleted raw rows" (Section 1, Section 10): once a batch is checkpointed, its cryptographic identity — the fact that a specific `merkle_root`, over a specific `seq` range, was attested to and signed under a specific key at a specific point in the chain — lives entirely in the `checkpoints` row and the tip chain built from it, not in the underlying `events` rows. The raw rows are evidentiary detail that can be discarded once their retention window closes; the checkpoint is the durable, compact proof that survives the discarding.

### 6.5 Worked edge case: a stream with events but no checkpoint yet

`chain_tip_hash` moving only in response to checkpointing, never to raw ingestion, has a corollary that surprises people the first time they see it: a stream can have any number of `events` rows — ten, ten thousand — and, as long as none of them have yet been rolled into a full `checkpoint_interval`-sized batch and checkpointed, its `chain_tip_hash` is still exactly `Genesis(stream_id)`, unchanged from the stream's very first moment of existence. Appending events does not, on its own, advance the tip chain — only checkpointing does. A stream with `checkpoint_interval = 1000` that has ingested its first 999 events sits with `chain_tip_hash = Genesis(stream_id)` and `checkpoint_count = 0` for as long as it takes to ingest the 1000th event and for the (out-of-scope-here) checkpointing process to cut the first checkpoint. This is normal, expected, and not a sign of anything being stuck — `verify`'s `event_count` field (Section 13.1) will correctly show 999 for such a stream even while `chain_tip_hash` shows the untouched genesis value, and both facts are simultaneously true and consistent.

### 6.6 Folding across streams: the whole-database tip

Section 13.1 defines `chain_tip_hash_overall`, the single top-level hash in `verify_report.json` that summarizes every stream in the database at once. Its construction is a direct extension of the per-stream tip chain: sort every stream in the database by `stream_id` (byte-wise ascending, the ordinary comparison for UTF-8 strings whose content is ASCII, which covers every `stream_id` in practice, per Section 3.2.1), and fold each stream's `stream_id` and `chain_tip_hash` into a single running hash:

```
chain_tip_hash_overall = SHA256(
  for each stream, sorted by stream_id ascending:
    BE16(len(stream_id)) || stream_id_bytes || chain_tip_hash_bytes(32)
)
```

There is no separate domain-separation prefix byte on this construction (it is not one of the four purposes enumerated in Section 4.1 — it is a report-level summary computed once per `verify` invocation, not a value that is ever itself folded into anything else downstream, so the collision concerns that motivate prefixing elsewhere do not apply to it in the same way). Worked example, folding the two streams from this section:

```
sorted order: "example-stream-001" (chain_tip_hash 84e97146...f52acc), "example-stream-002" (chain_tip_hash 34fd4312...9652c1f93)

fold input = BE16(19) || "example-stream-001" || 84e97146283735253c14119f3fe742217b445736257777b5ecae2dbc25f52acc
           ||  BE16(19) || "example-stream-002" || 34fd4312f16061e9e0c053e2ee251be0bd9601cb74021f61d047e9c9652c1f93

chain_tip_hash_overall = SHA256(fold input)
                        = 17ca833b2e1b96ac63cd43d2055949db0f82512cadfb447e9c511ed567b0f8ab
```

Every stream row in the database contributes to this fold, including a stream with zero events and zero checkpoints (which contributes its bare `Genesis(stream_id)` as its `chain_tip_hash`, per Section 6.5) — `chain_tip_hash_overall` summarizes the entire `streams` table, not merely the streams that happen to have interesting checkpoint history. Sorting by `stream_id` before folding is what makes this value deterministic and reproducible across runs and across the two subcommands: `streams` rows have no other stable, universal ordering to rely on (SQLite makes no guarantee about row iteration order absent an explicit `ORDER BY`), and folding in whatever order a query happens to return rows would make `chain_tip_hash_overall` a function of query-plan incidentals rather than of database content — exactly the kind of hidden nondeterminism this document tries to design out everywhere else, so it is designed out here too.

### 6.7 Edge cases

| Case | Behavior |
|---|---|
| Stream with zero events, zero checkpoints | `chain_tip_hash = Genesis(stream_id)`. Fully valid, not an error. Contributes normally to `chain_tip_hash_overall`. |
| Stream with events, zero checkpoints | `chain_tip_hash = Genesis(stream_id)`, unchanged from the row above, even though `event_count > 0`. See Section 6.5. |
| Stream fully pruned down to zero surviving events, but with checkpoints intact | `chain_tip_hash` is whatever the fold over its (untouched) `checkpoints` rows produces — pruning event rows never affects it, per Section 6.4. `event_count = 0`, `checkpoint_count` unchanged from before pruning. |
| Empty database (no `streams` rows at all) | `chain_tip_hash_overall = SHA256("")` — the fold over zero streams is the SHA-256 of the empty byte string. `streams` array in the report is empty. Not an error condition. |
| A single stream whose `stream_id` sorts before or after every other stream | No special handling — the fold is a straightforward ascending walk; first and last position in the sort order carry no special encoding. |

## 7. Checkpoint Signing Contract

### 7.1 Construction

```
CheckpointSigningBytes(stream_id, batch_index, start_seq, end_seq, merkle_root) =
    "CHAINAUDIT-CKPT-v1"
    || BE16(len(stream_id)) || stream_id_bytes
    || BE64(batch_index)
    || BE64(start_seq)
    || BE64(end_seq)
    || merkle_root                          // 32 bytes, no length prefix needed — fixed size

signature = HMAC-SHA256(key_material, CheckpointSigningBytes(...))
```

| Offset | Field | Length | Notes |
|---|---|---|---|
| 0–17 | magic | 18 | Fixed ASCII literal `"CHAINAUDIT-CKPT-v1"`, unprefixed (its length never varies, so there is nothing to prefix). |
| 18–19 | `stream_id_len` | 2 | Big-endian `uint16`, UTF-8 byte length of `stream_id` — same convention as Section 4.3. |
| 20–(19+N) | `stream_id` | N | UTF-8 bytes. |
| next 8 | `batch_index` | 8 | Big-endian `uint64`. |
| next 8 | `start_seq` | 8 | Big-endian `uint64`. |
| next 8 | `end_seq` | 8 | Big-endian `uint64`. |
| final 32 | `merkle_root` | 32 | Raw bytes, no length prefix — always exactly 32 bytes (a SHA-256 output), so there is nothing ambiguous about its boundary even without one. |

`key_material` is not part of `CheckpointSigningBytes` — it is the secret HMAC key, resolved separately via the Key Management service (Section 8) by `key_id`, and used only as the second argument to `HMAC-SHA256`, never hashed into the message itself. `signature` is always exactly 32 bytes (the output size of HMAC-SHA256), stored verbatim in `checkpoints.signature`.

### 7.2 Worked example

Using the first checkpoint of `example-stream-001` from Sections 5.6 and 6.3 (`batch_index = 0`, `start_seq = 0`, `end_seq = 3`, `merkle_root = 48fe1a47...f2806`):

| Offset | Field | Length | Hex |
|---|---|---|---|
| 0–17 | magic | 18 | `434841494e41554449542d434b50542d7631` (`"CHAINAUDIT-CKPT-v1"`) |
| 18–19 | `stream_id_len` | 2 | `0012` (18) |
| 20–37 | `stream_id` | 18 | `6578616d706c652d73747265616d2d303031` |
| 38–45 | `batch_index` | 8 | `0000000000000000` (0) |
| 46–53 | `start_seq` | 8 | `0000000000000000` (0) |
| 54–61 | `end_seq` | 8 | `0000000000000003` (3) |
| 62–93 | `merkle_root` | 32 | `48fe1a4765049c3a1797790204b7375de9c7a684f4ec2d89c5e6005d867f2806` |

Total length: **94 bytes**, concatenated:

```
434841494e41554449542d434b50542d763100126578616d706c652d73747265616d2d30303100000000000000000000000000000000000000000000000348fe1a4765049c3a1797790204b7375de9c7a684f4ec2d89c5e6005d867f2806
```

For illustration only — never a real production key — suppose `key_id = "kms-2024-06-a"` resolves (Section 8.1) to the 32-byte key material `000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f` (the bytes `0x00` through `0x1f` in order; chosen here purely because it's trivially reproducible by hand, not because real KMS key material looks like this — real key material is uniformly random). Then:

```
signature = HMAC-SHA256(0x000102...1e1f, <the 94 bytes above>)
          = 316c875b204e558f81f195a4156ccd832331e6ef59dc9a99041f35901b8fdfc4
```

This is the value stored in that checkpoint's `signature` column. The second checkpoint of the same stream (`batch_index = 1`, `start_seq = 4`, `end_seq = 7`, `merkle_root = 4933572c...fa4816`), signed under the same illustrative key:

```
CheckpointSigningBytes = 434841494e41554449542d434b50542d763100126578616d706c652d73747265616d2d3030310000000000000001000000000000000400000000000000074933572c4aad4fddb945232ce13a055b502c82aff1de6f0901b2ec7724fa4816

signature = HMAC-SHA256(0x000102...1e1f, <the 94 bytes above>)
          = a23d2323bf383ea11e4c8005bf6571ff8a9f5cdcf8bf1b8bde7356b475b45458
```

And `example-stream-002`'s single checkpoint (`batch_index = 0`, `start_seq = 0`, `end_seq = 4`, `merkle_root = 439c0ee7...a037412`, `key_id = "kms-2024-03-a"`, same illustrative key material for this worked example):

```
CheckpointSigningBytes = 434841494e41554449542d434b50542d763100126578616d706c652d73747265616d2d303032000000000000000000000000000000000000000000000004439c0ee7525abdc4b24b2c60456bc12a7342053ac8b951406e1b55824a037412

signature = HMAC-SHA256(0x000102...1e1f, <the 94 bytes above>)
          = 08d64ea2eb89e4067d12d72fdd1a67783eae819f82a951d76d9e266b07e96e13
```

Notice `example-stream-001` batch 0 and `example-stream-002` batch 0 share almost every structural field — both are `batch_index = 0`, both have `start_seq = 0`, and their `stream_id_len` is identical (18 bytes for both `"example-stream-001"` and `"example-stream-002"`, differing only in their final digit) — yet produce entirely unrelated signing-byte sequences and entirely unrelated signatures, because `stream_id`, `end_seq`, and `merkle_root` all differ. This is exactly the property Section 7.3 explains the rationale for.

### 7.3 Why bind stream and batch coordinates instead of signing the bare root

A simpler design would sign only the `merkle_root` itself: `HMAC-SHA256(key_material, merkle_root)`. ChainAudit does not do this, and the reason is worth stating precisely rather than gesturing at "defense in depth." A bare-root signature is a signature over a 32-byte value with no context — it attests only "some Merkle tree with this root was signed under this key," not "*this specific batch, of this specific stream*, was signed under this key." Two different batches — even two different *streams* — could in principle produce the same `merkle_root` (SHA-256 gives no structural guarantee against this beyond ordinary collision resistance, and while a genuine SHA-256 collision is not a realistic near-term threat, *coincidental* equality of two Merkle roots computed over genuinely different underlying event sets is a different and much weaker property to rely on, especially as the number of checkpoints accumulated across a large multi-tenant system grows over years). If only the bare root were signed, a valid signature computed for one batch would also, by definition, be a valid signature for any other (batch, stream) pair that happened to produce the identical root — the signature carries no information tying it to *which* batch it was meant for.

By binding `stream_id`, `batch_index`, `start_seq`, `end_seq`, and `merkle_root` all together into the signed message, a signature is only ever valid for the exact combination of stream, batch position, sequence range, and root it was computed over. Even in the (again, cryptographically remote but not thereby uninteresting) event that two batches shared a `merkle_root`, their `CheckpointSigningBytes` would still differ — different `stream_id` or different `start_seq`/`end_seq` — and so would their signatures, unless an attacker also controlled the HMAC key, at which point the signature scheme's guarantees have failed for an entirely different and more fundamental reason than root reuse. This binding is what lets `verify`'s signature check be phrased as precisely as it is in Section 8.3 and Section 13.1: a signature check is a check of *this checkpoint*, not a check of *some checkpoint that happens to share this root*.

### 7.4 `key_id` is metadata, not a hashed secret

`key_id` appears in two different hash constructions in this document — folded into the tip chain (Section 6.2) and, implicitly, as the lookup key `verify` uses to resolve `key_material` from the Key Management service (Section 8) before computing `HMAC-SHA256` — but it never appears inside `CheckpointSigningBytes` itself. This is intentional: `CheckpointSigningBytes` is the message being authenticated, and `key_id` is bookkeeping about *which key* authenticated it, conceptually adjacent to the signature rather than part of the signed content. Folding `key_id` into the tip chain (but not into the signed bytes) means a checkpoint's tip-chain contribution reflects which key was used, so that a key substitution — even one that somehow produced a validly-re-signed checkpoint under a *different* key than originally used — would still change `chain_tip_hash`, even if it wouldn't change whether the signature itself currently validates.

### 7.5 Edge cases

| Case | Behavior |
|---|---|
| `signature` is not exactly 32 bytes | Not producible by any sanctioned write path (`HMAC-SHA256` always outputs 32 bytes). If encountered on a stored row, this is itself a structural anomaly — `verify` cannot recompute a meaningful comparison against a `signature` field of the wrong length and treats it as a signature check failure (`tampered_checkpoint_signature`, assuming the key itself resolves successfully; see Section 8.3) rather than crashing or silently skipping the checkpoint. |
| Two checkpoints (different streams) share a `merkle_root` | No special handling needed — see Section 7.3; their `CheckpointSigningBytes` still differ because `stream_id` differs, so their signatures are independent. |
| Two checkpoints (same stream) share a `merkle_root` | Would require an actual SHA-256 collision across the two different underlying leaf sets, or two checkpoints being cut over the exact same `seq` range with the exact same leaf contents (which `batch_index`/`start_seq`/`end_seq` uniqueness rules out for the same stream) — not a case this document treats as reachable in practice. |
| `key_id` references a key that was never valid (typo, wrong environment) | Indistinguishable, from `verify`'s perspective, from a key that is currently unreachable or revoked — the KMS lookup fails or returns a non-`200` status, and the checkpoint's signature cannot be positively confirmed. See Section 8 for the full classification. |

## 8. Key Management Service API Reference

### 8.1 Endpoint

```
GET {kms_addr}/v1/keys/{key_id}
```

`{kms_addr}` is a base URL, for example `http://127.0.0.1:8500`, supplied to `verify` via `--kms-addr` (Section 12.1). `{key_id}` is the opaque string stored in a checkpoint's `key_id` column (Section 3.4), URL-path-escaped if it contains characters that require it (in practice, `key_id` values are chosen from a restricted charset by the Key Management team specifically to avoid ever needing escaping, but `verify`'s HTTP client does not assume this and escapes defensively regardless).

This is the only HTTP call ChainAudit ever makes. `compact` never calls it — pruning eligibility depends only on timestamps and hold flags (Section 10), never on whether a checkpoint's signature is currently verifiable, so `compact` has no reason to reach the network at all, and does not. Only `verify`'s signature-checking step (Section 8.3, Section 13.1) calls this endpoint, once per distinct `key_id` encountered across all of a database's checkpoints — `verify` deduplicates lookups within a single run rather than issuing one request per checkpoint row, since a single `key_id` is typically shared across many checkpoints (an operational key is normally rotated on a schedule measured in months, while checkpoints for an active stream are cut far more often than that).

### 8.2 `200 OK` — key is active

```json
{
  "key_id": "kms-2024-06-a",
  "key_material_hex": "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
}
```

`key_material_hex` is 64 hex characters — 32 bytes — decoded and used directly as the raw HMAC-SHA256 key, with no further derivation, key-stretching, or transformation applied. (The example value above is the same illustrative, non-production key material used throughout the worked examples in Sections 6 and 7; real key material returned by the production Key Management service is cryptographically random and is never logged, persisted by ChainAudit beyond the lifetime of a single `verify` process's memory, or written into any report.) A `200` response means the key identified by `key_id` is currently active and its material can be used to attempt a signature check; it does not, on its own, mean the signature check will succeed — an active key and a mismatched signature together are exactly the `tampered_checkpoint_signature` case in Section 8.5 below.

### 8.3 `410 Gone` — key has been rotated out, and why that is not the same as failure

```json
{
  "error": "key_rotated",
  "key_id": "kms-2024-06-a",
  "message": "this key was rotated out of service and its material is no longer available"
}
```

(The exact shape of the error body beyond a `410` status is informational rather than part of the contract `verify` depends on — `verify` keys its behavior off the HTTP status code alone; the JSON body, when present, is surfaced in logs for human debugging but no field within it drives verification logic.)

A `410` means the key that signed one or more checkpoints has since been rotated out of active service — a normal, expected, entirely routine lifecycle event for any managed key, wholly independent of whether anything is wrong with the data those checkpoints cover. This is the single most consequential distinction in this entire document to get right, so it is worth stating as bluntly as possible:

> **A `410` is not a failure to be treated the same as any other error, and it is absolutely not, on its own, evidence of tampering.** A checkpoint signed with a key that has since been rotated out cannot be cryptographically *re-verified* — there is no way to recompute `HMAC-SHA256` against material that is no longer available — but the *inability to reverify* is not the same fact as *the checkpoint having been tampered with*. Those are two different statements, and this system is careful never to conflate them.

The correct classification, stated precisely: a stream where every check that *can* still be performed — the per-event content check (recomputing `leaf_hash` from current row state and comparing to stored `leaf_hash`, Section 4.4, Section 4.9) and the structural check (recomputing each intact checkpoint batch's Merkle root from stored leaf hashes and comparing to stored `merkle_root`, Section 5) — passes cleanly, but where one or more checkpoints reference a key that returns `410`, is reported as `legacy_unverifiable`, never `corrupt`. A stream is only ever `corrupt` if something *concretely* fails to check out: a content mismatch, a structural (Merkle root) mismatch, or a genuine HMAC mismatch against a key that is still active. Key rotation, by itself, proves nothing about data integrity in either direction — it only means one particular *kind* of check (cryptographic signature confirmation) is no longer available for that specific checkpoint, and every other kind of check keeps running regardless and can still surface real corruption entirely independent of key status. **A stream is never silently "clean" merely because a key was revoked** — revocation narrows what can be positively confirmed; it never widens what gets skipped.

#### 8.3.1 Worked contrast: two streams that both fail their signature check, for different reasons

Consider two streams, both of which fail to produce a confirmable signature for their most recent checkpoint. On the surface, the immediate symptom looks identical in both cases — `verify` cannot say "yes, this signature is valid." The correct diagnosis, and the correct JSON output, are entirely different.

**Stream P:** its checkpoint's `key_id` resolves against the KMS with a `410`. Nothing else is wrong — every event's content check passes, and (Section 5.7) the checkpoint's Merkle root recomputes cleanly against its stored leaf hashes (assuming the batch is still intact; Section 10.6 covers the fully-pruned case separately). The correct verdict for Stream P: `status = "legacy_unverifiable"`, `reason = "revoked_key"`, `revoked_key_ids = ["kms-2024-06-a"]` (or whichever `key_id` was involved), `first_bad_seq = null`, `first_bad_batch = null`. Nothing is reported as corrupt, because nothing has been shown to be corrupt — the honest, precise statement about Stream P is "this specific cryptographic confirmation is no longer obtainable," not "this data is untrustworthy."

**Stream Q:** its checkpoint's `key_id` resolves against the KMS with a `200` and perfectly good key material — the key is fully active. But when `verify` recomputes `HMAC-SHA256(key_material, CheckpointSigningBytes(...))` using that active key, the result does not match the checkpoint's stored `signature` — someone (or something) has altered the stored `signature` bytes, or altered one of the fields folded into `CheckpointSigningBytes` (`start_seq`, `end_seq`, or `merkle_root`) without correspondingly updating `signature` to match. The correct verdict for Stream Q: `status = "corrupt"`, `reason = "tampered_checkpoint_signature"`, `first_bad_batch` set to that checkpoint's `batch_index`. This *is* evidence of tampering — an active key, capable of producing a definitive answer, produced a definitive "no."

Both streams present the same superficial symptom to someone glancing only at "did the signature check pass? No." Both would, if reported carelessly, look equally alarming. But Stream P's correct report should not alarm anyone — it should prompt, at most, a shrug and a note that historical data signed under a now-rotated key can no longer have its signature freshly confirmed, which is an expected and permanent consequence of key rotation policy, not an incident. Stream Q's correct report should alarm everyone who sees it — it is exactly the signal this entire system exists to produce. Collapsing these two into one status value, or worse, into one *severity*, would either desensitize operators to the one case that matters (by crying wolf every time a key rotates on schedule) or — far worse — bury a real corruption finding under a flood of routine, expected rotation-driven `legacy_unverifiable` noise that operators have learned to ignore. Section 13.1's `reason` field exists specifically so these two situations are never reported identically, and Section 14 has several FAQ entries walking through what to do operationally with each.

> **Open question (Marcus, 2024-06-25):** Should `status` itself have a fourth value to separate "key rotated, definitely fine otherwise" from "KMS unreachable right now, unknown"? They don't feel like the same situation operationally — one is permanent and expected, the other is transient and might resolve itself if you just run `verify` again in five minutes. Flagging this for discussion before we finalize the JSON schema.
>
> **Resolved 2024-07-02 — see Changelog.** `status` stays at exactly three values; `reason` is the field that carries this distinction (`revoked_key` versus `kms_unavailable`), both of which map to the same `legacy_unverifiable` status. Rationale recorded in Section 16.

### 8.4 `429 Too Many Requests` — transient rate limiting

A `429` means the Key Management service is asking its caller to slow down. This is not a data-integrity signal of any kind — it says nothing about any checkpoint's validity — and it is not, on its own, grounds for reporting `kms_unavailable` after a single occurrence. Clients calling this endpoint **must** implement retry with exponential backoff plus jitter; hammering the endpoint in a tight retry loop is explicitly against policy, and is not a hypothetical concern — see the 2024-11-04 changelog entry for the incident that resulted from exactly this mistake, made by a different internal tool rather than by ChainAudit itself, which nonetheless degraded the Key Management service for every consumer, ChainAudit included, for the better part of an afternoon.

This document deliberately does not specify an exact retry count or exact backoff constants as a hard requirement. That is a considered choice, not an oversight: a fixed "retry exactly 5 times with exactly a 200ms base delay" recipe tends to age badly — it gets copy-pasted into client after client without anyone revisiting whether it's still appropriate as load patterns change, and it invites exactly the kind of synchronized-retry-storm behavior that backoff and jitter exist to prevent in the first place, if enough independent clients all happen to be configured with the identical fixed schedule. Instead: clients should back off exponentially with jitter, and give up after a small, bounded number of attempts, logging a clear, specific error when they do give up (naming the `key_id`, the number of attempts made, and the final status or error observed) rather than failing silently or looping indefinitely. What counts as a reasonable bound is an engineering judgment call for whoever is operating a given client at a given time, informed by how urgent that particular `verify` run is and how the Key Management service's current health looks — this document trusts implementers to make that call rather than prescribing a number that would inevitably be wrong for someone's situation.

### 8.5 Any other status — genuine service error

Any HTTP status other than `200`, `410`, or `429` — a `500`, a `503`, a connection timeout, a connection refused, a malformed response body that fails to parse as the expected JSON shape — is a genuine service error. `verify` treats this the same way it treats a `429` that has exhausted its retry budget: the specific checkpoint's (and by extension, the specific stream's) signature cannot be checked this run, `reason = "kms_unavailable"`, `status = "legacy_unverifiable"` provided nothing else about the stream is independently broken. Unlike `revoked_key`, `kms_unavailable` is not expected to be a durable, permanent fact about a specific key — it is expected, in the ordinary case, to be transient, and re-running `verify` once the Key Management service has recovered will typically resolve a stream out of `kms_unavailable` and into whatever its true status is. `verify` does not retry a `kms_unavailable` outcome automatically across separate invocations (there is no persistent retry queue or state carried between runs); re-running the whole `verify` command is the operational mechanism for retrying, once whatever caused the outage has cleared.

> **Open question (Dana, 2024-11-05):** Should `first_bad_batch` be populated for a checkpoint that hit `kms_unavailable` or `revoked_key`, so operators have a specific batch coordinate to look at instead of just a stream-level status? Right now it seems to stay `null` for both.
>
> **Resolved 2024-11-18 — see Changelog.** No: `first_bad_batch` is reserved for checkpoints where a check was actually *performed* and *failed* (structural mismatch, or a genuine signature mismatch against an active key) — Section 13.1's field description says "structural or signature check **fails**," and a `410` or a KMS outage means the signature check could not be *attempted* at all, which is a different situation from attempting it and getting a negative result. `revoked_key_ids` (Section 13.1) is the actionable breadcrumb for the revoked-key case, naming which keys need rotation-aware attention; there is deliberately no equivalent per-batch breadcrumb array for `kms_unavailable`, since that condition is expected to be transient and self-resolving on a re-run rather than something to individually enumerate and track. See Section 14 for the operational FAQ entry walking through what to actually do when you see each.

### 8.6 Status code summary

| HTTP status | Meaning | `verify` classification | Contributes to |
|---|---|---|---|
| `200 OK` | Key is active; material returned | Signature check proceeds using the returned key material | `ok` (if signature matches) or `corrupt` / `tampered_checkpoint_signature` (if it doesn't) |
| `410 Gone` | Key has been rotated out | Signature check cannot be attempted for this checkpoint | `legacy_unverifiable` / `revoked_key` (unless the stream is independently `corrupt` for an unrelated reason — see Section 8.7 precedence rules) |
| `429 Too Many Requests` | Transient rate limiting | Retry with backoff and jitter; if retries are exhausted, treated as a service error | `legacy_unverifiable` / `kms_unavailable` if exhausted |
| Any other status, timeout, or connection failure | Genuine service error | Signature check cannot be attempted for this checkpoint | `legacy_unverifiable` / `kms_unavailable` |

### 8.7 Precedence when a stream has multiple, different findings

A single stream can, in principle, encounter more than one of these outcomes at once — one checkpoint's key might be revoked while a completely different event in the same stream has a content mismatch, for instance. Because `verify_report.json`'s per-stream `status` and `reason` fields (Section 13.1) are single values, not arrays, ChainAudit applies a fixed precedence order to decide which single `reason` is reported when multiple distinct findings coexist for the same stream. From highest to lowest precedence:

1. **`tampered_event`** — any content-check failure anywhere in the stream (checkpointed or in the uncheckpointed tail). Direct evidence of row-level tampering; always wins.
2. **`tampered_merkle_root`** — any structural mismatch on an intact checkpoint batch, including the partial-batch anomaly (Section 3.5.5) and the non-contiguous-`batch_index` anomaly (Section 3.5.4).
3. **`tampered_checkpoint_signature`** — any signature mismatch against a currently-active key.
4. **`revoked_key`** — any checkpoint whose key returned `410`, provided nothing higher in this list was also found.
5. **`kms_unavailable`** — any checkpoint whose key lookup failed for a transient or service-level reason, provided nothing higher in this list was also found.
6. **`null`** — nothing wrong found anywhere in the stream.

The first three map to `status = "corrupt"`; the fourth and fifth map to `status = "legacy_unverifiable"` (with reason 6 mapping to `status = "ok"` instead, since `reason = null` and `status = "ok"` are the same statement made twice). Note carefully that this precedence governs only which single `reason` string is surfaced — `first_bad_seq` and `first_bad_batch` are populated independently of this precedence order, each reflecting the lowest offending `seq` or `batch_index` for its own respective check category regardless of which finding ultimately "wins" the `reason` field. An operator triaging a `corrupt` stream should always inspect both `first_bad_seq` and `first_bad_batch` directly rather than assuming the named `reason` is the only thing wrong — a stream can easily have both a content-check failure and a structural failure simultaneously, and both fields will be populated to reflect that even though `reason` can only name one of them.

### 8.8 Raw request and response transcripts

For anyone implementing or debugging a client against this contract directly (rather than through the reference Go client), the three status codes in full, as raw HTTP — the actual wire-level shape, not just the parsed JSON already shown in Sections 8.2 through 8.4:

**Request** (identical in shape regardless of outcome):

```
GET /v1/keys/kms-2024-06-a HTTP/1.1
Host: 127.0.0.1:8500
Accept: application/json
```

(Authentication, if the deployment environment requires any beyond network-level access control to reach `--kms-addr` at all, is handled via whatever transport- or header-level credential convention that specific deployment's Key Management service expects — this is an environment-specific operational detail, not part of the wire contract this document specifies, and is out of scope here in the same way TLS configuration for `--kms-addr` itself is.)

**`200` response:**

```
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 94

{"key_id":"kms-2024-06-a","key_material_hex":"000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"}
```

**`410` response:**

```
HTTP/1.1 410 Gone
Content-Type: application/json
Content-Length: 118

{"error":"key_rotated","key_id":"kms-2024-06-a","message":"this key was rotated out of service and its material is no longer available"}
```

**`429` response** (note the `Retry-After` header — present as a hint on the production Key Management service's actual responses, and a reasonable signal for a client's backoff calculation to take into account, though Section 8.4 deliberately does not mandate that a client's backoff schedule be driven strictly by this header's value, since not every KMS-contract-compatible server a client might be pointed at, including `mockkms` in some configurations, is guaranteed to set it):

```
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 2
Content-Length: 45

{"error":"rate_limited","key_id":"kms-2024-06-a"}
```

A client parsing these responses should key its behavior off the numeric status line (`200`, `410`, `429`) exclusively for the purposes of the classification described in Sections 8.2 through 8.5 — the JSON body fields (`error`, `message`) are for human-readable logging (Section 15.4's example stderr lines draw directly from fields like these) and are not validated against a fixed schema beyond `200`'s `key_id` and `key_material_hex`, which `verify` does parse and depend on structurally (a `200` with a missing or malformed `key_material_hex` is the `kms_bad_response` condition in Section 15.4, treated as a service error despite the `200` status, precisely because the status code alone told only part of the story in that specific case).

### 8.9 Local reference implementation

As introduced in Section 2.3, `cmd/mockkms` implements this exact contract for local development, staging rehearsal, and operational drills. Pointing `--kms-addr` at a running `mockkms` instance configured with a key entry set to return `410` is the standard way to safely rehearse what a `legacy_unverifiable` / `revoked_key` report looks like without needing to coordinate an actual key rotation against the production Key Management service; a key entry configured to return `429` for the first several requests before flipping to `200` is the standard way to exercise and observe a client's backoff-and-retry behavior end to end.

## 9. Tombstones and Right-to-Erasure Semantics

### 9.1 What erasure means in this system, and what it deliberately does not mean

"Right-to-erasure" here refers to any compliance obligation — a data-subject deletion request, a data-minimization policy trigger, a contractual data-handling term — that requires the sensitive content of a specific event's `payload` to stop existing in storage. It does not mean, and is never used to mean, "make it as though this event never happened." Those are two different obligations, and this system is deliberately built to satisfy only the first one through tombstoning, while the second — actually removing a row so that its very existence is no longer represented anywhere, including in aggregate counts and Merkle-covered ranges — is `compact`'s job under retention policy (Section 10), governed by age and legal hold, never by an erasure request directly.

This separation is intentional and worth justifying rather than simply asserting. An audit log's core value proposition is that it can answer "what happened, and when, and did anyone tamper with the record of it" — and that value proposition depends on the *shape* of history (how many events occurred, in what order, of what types, at what times) remaining intact and provable even when the *sensitive content* of a specific event must be redacted for an unrelated legal reason. If honoring an erasure request meant deleting the row outright, every erasure would also silently rewrite history — collapsing `seq` ranges, invalidating checkpoint spans that assumed a fixed count of events, and making it impossible to later prove "yes, an event of this type happened at this time, and its content was subsequently and lawfully erased" versus "no event ever happened here at all." Tombstoning exists so that erasure and forgetting-that-something-happened are not the same operation, and only the latter is destructive.

### 9.2 What the erasure path actually changes

Recall from Section 3.3.3: exactly one process, external to the `chainaudit` CLI itself — the compliance team's data-subject-request tooling, referred to in this document as **the erasure path** — is permitted to transition an event from its original state to tombstoned, and it does so atomically, in a single transaction, changing exactly three things:

1. The `payload` column is cleared (its prior contents actually leave storage — this is the entire point; a "soft delete" that leaves recoverable sensitive bytes sitting in a column with only a flag distinguishing it is not an erasure implementation this system considers acceptable, even though nothing in the SQLite schema itself would prevent someone from building a non-compliant version of the erasure path that did that).
2. `tombstone` is set to `1`.
3. `leaf_hash` is recomputed against the sentinel-substituted canonical encoding (Section 4.7) and the stored value is overwritten.

Everything else about the row is untouched: `stream_id`, `seq`, `ts`, `event_type`, and `legal_hold` all keep whatever values they had before erasure, and all of them remain part of the hashed canonical encoding exactly as before. This is deliberate — the *fact* that an event of a given type occurred at a given time, at a given position in the stream, remains fully part of the tamper-evident record; only the event's *payload content* is what erasure removes. A compliance reviewer, or an auditor, or a future `verify` run, can still confirm precisely how many `"user.delete_request"` events a stream contains and exactly when each occurred — they simply cannot recover what any given one of them actually said, once tombstoned.

### 9.3 Origin: the ambiguity incident

The sentinel-substitution design described byte-for-byte in Section 4.7 was not the original implementation. The first production version of the erasure path (predating the tombstone sentinel by roughly a month — see the 2024-04-29 and 2024-05-06 changelog entries) implemented erasure by clearing `payload` to a zero-length value and leaving the rest of the canonical encoding's payload-related fields (`payload_marker`, `payload_len`) computed exactly as they would be for any other zero-length payload — because at the time, nothing in the encoding format distinguished "erased" from "never had one" as a payload *shape*, only the separately-stored `tombstone` column recorded the distinction, and that column's value, at the time, was not yet part of the hashed encoding at all for the payload-shape question (it existed, but the encoding logic didn't yet key off it to select a different payload representation).

The practical consequence discovered in production: routine compliance spot-checks comparing the *count* of tombstoned events (queried directly from the `tombstone` column) against what a byte-level inspection of the hashed encoding could independently corroborate found that the encodings for erased events and for legitimately-payload-free events (a family of low-volume system event types that had never carried a payload) were structurally identical in shape, differing only in the fields that were always going to differ anyway (`seq`, `ts`). Nothing was cryptographically broken — every hash still matched what was stored, and no tampering had occurred — but the hashed record itself carried no independent trace that erasure, specifically, had happened; the only evidence was the unhashed-for-this-purpose `tombstone` column, which a sufficiently motivated internal party with direct database access could in principle have flipped back to `0` without changing any encoding-derived hash at all, since at that time `tombstone` fed the encoding only through the already-cleared `payload` bytes, not through a dedicated, unmistakable marker. This is what prompted the sentinel redesign: making `payload_marker`, `payload_len`, and `payload_bytes` all diverge sharply and unconditionally between "erased" and "never had a payload" closes that gap, because the tombstoned encoding shape (marker `0x01`, length `32`, sentinel bytes) cannot be produced by any other combination of inputs, and the `tombstone` column's truthfulness becomes something the hash itself corroborates rather than something taken on faith from an unhashed-in-effect flag.

### 9.4 Erasure and legal hold are independent axes

An event can simultaneously be tombstoned (`tombstone = 1`) and under legal hold (`events.legal_hold = 1`, or covered by whole-stream `streams.legal_hold = 1`), and this is not a contradiction. The two flags govern two different operations entirely:

- `tombstone` governs whether the *payload content* has been redacted. It is set once, by the erasure path, and never unset.
- `legal_hold` governs whether the *row* is exempt from pruning by `compact` (Section 10). It can be set and cleared independently, by whatever process manages litigation holds, entirely separate from the erasure path.

A concrete, realistic scenario where both apply: an event is lawfully erased in response to a data-subject request — its payload is redacted, `tombstone` becomes `1`. Some time later, that same event's stream (or that specific event) becomes relevant to litigation, and legal hold is placed on it to preserve *the record that this event occurred, and when* — the row itself, `seq`, `ts`, `event_type`, and the fact of its (already-completed, already-lawful) erasure — from being pruned while the litigation is active. This is entirely coherent: legal hold is not a claim that the payload content is being preserved (it was already lawfully redacted, and legal hold does not and cannot un-redact it), only that the row's continued existence — including the fact that it was erased — is being preserved for the duration of the hold. `compact` honors `legal_hold` exactly the same way for a tombstoned row as for any other row: if `legal_hold = 1`, that row blocks its entire containing batch from pruning (Section 10.4), regardless of whether the row's payload happens to be a live value or a sentinel.

The reverse ordering is equally valid and equally common: an event already under legal hold can still be lawfully tombstoned if an erasure obligation independently applies to it. Legal hold prevents *deletion*; it does not, and is not intended to, prevent *payload redaction* — those remain two different operations governed by two different teams' obligations, and neither this document nor the schema it describes treats one as blocking the other.

### 9.5 Erasure against an already-checkpointed event

This is the subtlest interaction in this section, worth working through carefully rather than glossing over, because getting it wrong either way — assuming it can't happen, or assuming it's silently harmless — leads to real operational confusion.

Because `leaf_hash` is recomputed and overwritten at the moment of erasure (Section 3.3.3, Section 9.2), and because a checkpoint's `merkle_root` was computed once, at checkpoint-creation time, from whatever `leaf_hash` values were present *then*, erasing the payload of an event that was already covered by an existing checkpoint changes that event's `leaf_hash` out from under a `merkle_root` that already committed to the *old* value and can never be recomputed or re-signed (checkpoints are immutable — Section 3.4, Section 2.6 — there is no mechanism anywhere in this schema to revise a `merkle_root` or reissue a `signature` for an existing `batch_index`). The direct consequence: from the moment of erasure until that batch is later pruned, `verify`'s structural check for that specific batch (Section 5, recomputing the batch's Merkle root from current `leaf_hash` values and comparing to the checkpoint's stored `merkle_root`) will no longer match, and will correctly report `tampered_merkle_root` with `first_bad_batch` set to that checkpoint's `batch_index` — even though nothing about this situation involves tampering in the adversarial sense the reason code's name implies.

This is accepted, intentional behavior, not a defect to be engineered away, because there is no coherent alternative: the checkpoint's signature already committed, permanently, to a specific `merkle_root` over a specific set of leaf hashes, and honoring a lawful erasure request cannot be made contingent on waiting for that batch to age out and get pruned — compliance deadlines for erasure obligations do not bend to internal checkpoint bookkeeping. The system's answer is to let the structural check fail honestly, exactly as it would for a batch that was genuinely tampered with, because from the narrow perspective of "does this stored `merkle_root` still match what these `leaf_hash` values fold to," the two situations produce an identical, correct, negative answer — the difference is entirely in *why* the leaves changed, which is not information the Merkle recomputation has access to.

**Worked example.** Take `example-stream-001`'s first checkpoint batch again (Section 5.6): `seq 0`–`3`, stored `merkle_root = 48fe1a4765049c3a1797790204b7375de9c7a684f4ec2d89c5e6005d867f2806`, already signed. Suppose `seq 1` (`"user.mfa_challenge"`, v1, originally `{"user_id":"u_4471","method":"totp"}`, `leaf_hash = c92b44f3de197605985b406b00a50c5120b4ffe1171ababf2a920bd3a6b0cb20`) is lawfully tombstoned some time after this checkpoint was cut. The erasure path clears its payload, sets `tombstone = 1`, and recomputes its `leaf_hash` under the sentinel-substitution rule — still v1-encoded (tombstoning doesn't affect version selection, Section 9.7), so still no trailing `legal_hold` byte, but now with `payload_marker = 0x01` and the 32-byte sentinel in place of the original payload:

```
new leaf1 encoding = 0100126578616d706c652d73747265616d2d303031000000000000000100000000664b18180012757365722e6d66615f6368616c6c656e6765010000002032d3bbf3adec96389385454fce1451dd2bd7ca45ee947d4fcd012d543cc78d1f
new leaf1 = SHA256(0x00 || <above>) = bd99b4a52f6dc29219a080e8524ea4fd7265bdd545eef60333edb60b7ea98e1e
```

The next time `verify` runs, it recomputes this batch's structural check using the *current* `leaf_hash` values — `leaf0` and the new, post-erasure `leaf1`, alongside the unchanged `leaf2` and `leaf3`:

```
node(leaf0, new_leaf1) = SHA256(0x01 || leaf0 || bd99b4a5...b7ea98e1e) = cfd6eadde7e3dfc02c57dcb120e25093d5fae17e00d058ecc734ba0751bcb1b3
node(leaf2, leaf3)     = 816958285b579eb569ddbb99c41b230e862df055ed9f8f653ab311d02d76caa3   (unchanged — Section 5.6)

recomputed root = SHA256(0x01 || cfd6eadd...1bcb1b3 || 816958285b57...02d76caa3)
                = ca836f96f657423a92960a2538a5256fdca5a63bf72712c7da38429cfce5778c
```

`ca836f96f657423a92960a2538a5256fdca5a63bf72712c7da38429cfce5778c` does not equal the checkpoint's stored `48fe1a4765049c3a1797790204b7375de9c7a684f4ec2d89c5e6005d867f2806` — nor should it. This mismatch is `verify`'s `tampered_merkle_root` finding for `batch_index = 0`, produced mechanically and correctly by the same recomputation Section 5 always performs, with no awareness on the algorithm's part that the changed leaf came from a sanctioned erasure rather than an attack. This is the concrete arithmetic behind the prose two paragraphs above, and behind the triage walkthrough in Section 15.6 — an operator seeing exactly this pair of root values in a real `verify` report, for a batch where the compliance erasure log confirms a `seq 1` erasure at the right time, has now seen precisely why they don't match and precisely why that's expected.

The consequence resolves itself once the batch becomes eligible for pruning (Section 10) and is pruned: once a batch's `events` rows are gone, `verify` stops attempting structural recomputation for it entirely (Section 5.7, Section 10.6) and relies solely on the checkpoint's signature, which is unaffected by anything that ever happened to the (now-deleted) rows' `leaf_hash` values — the signature was always over `merkle_root` and the batch's coordinates, never over the leaves directly, and remains fully valid. In practice, this means a batch containing a legitimately-erased event will show `tampered_merkle_root` for however long remains between the erasure and that batch's eventual pruning, and this is expected. Operators triaging a `tampered_merkle_root` finding should cross-reference the affected `seq` range (obtainable from the checkpoint's `start_seq`/`end_seq`, given `first_bad_batch`) against the compliance team's erasure log — maintained by the erasure path's own tooling, outside ChainAudit's scope — before escalating a finding as a suspected genuine incident. This cross-referencing step is manual and operational, not automated by `verify` itself; the JSON report's fixed `reason` enum (Section 8.7, Section 13.1) has no separate code for "structural mismatch, but explained by a known lawful erasure," and is not expected to grow one — see Section 14 for the corresponding FAQ entry on triaging this specific situation.

### 9.6 Re-erasure and idempotency

An event that is already tombstoned (`tombstone = 1`) is not expected to be presented to the erasure path a second time under normal operation, and the erasure path's own idempotency handling (ensuring a second erasure request against an already-tombstoned event is a safe no-op rather than a second overwrite of `leaf_hash`) is that tooling's responsibility, not something `chainaudit verify` or `chainaudit compact` enforce or check. From ChainAudit's perspective, an event's canonical state changes at most once after ingestion — the one-way transition described in Section 3.3.3 — and everything in this document assumes that invariant holds. A row that has somehow been tombstoned, un-tombstoned, and re-tombstoned (which would require bypassing the erasure path's own safeguards, since nothing about `tombstone = 1` is reversible through any sanctioned path) is outside the set of states this document describes, and `verify` would have no way to distinguish it from ordinary tampering — which, from a tamper-evidence standpoint, is exactly the correct outcome: an unsanctioned reversal of a tombstone is precisely the kind of unauthorized modification this whole system exists to catch.

### 9.7 Edge cases

| Case | Behavior |
|---|---|
| Event tombstoned and under per-event `legal_hold = 1` simultaneously | Fully valid (Section 9.4). `compact` still treats the row as blocking its batch from pruning, same as any other legal-held row, tombstoned or not. |
| Event tombstoned, stream under whole-stream `legal_hold = 1` | Same as above — whole-stream hold blocks every batch in the stream regardless of any individual row's tombstone status. |
| Erasure requested against an event still in the uncheckpointed tail | No structural-check consequence at all (Section 9.5's issue only arises for checkpointed batches) — the content check continues to pass cleanly, and there is no checkpoint yet to become inconsistent. This is the operationally "clean" case. |
| Erasure requested against an event in an already-checkpointed, not-yet-pruned batch | Structural check for that batch reports `tampered_merkle_root` from the moment of erasure until the batch is pruned. Expected and intentional — see Section 9.5. |
| Erasure requested against an event whose batch has already been pruned | Not applicable — the row is gone; there is nothing left to erase, and the compliance team's tooling would report the request as already moot (the payload no longer exists in ChainAudit's storage at all, having been removed by pruning rather than by erasure). |
| A v1-encoded event is tombstoned | The tombstone rule applies identically regardless of encoding version (Section 4.3's byte layout table lists `payload_marker`/`payload_len`/`payload_bytes` as shared fields, not version-gated) — only the presence or absence of the trailing `legal_hold` byte differs between v1 and v2, and that is unrelated to tombstoning. |
| Attempting to query what a tombstoned event's original payload was | Not recoverable through ChainAudit or through the database at all — the actual bytes are gone from `payload`, and the sentinel that replaces them in the canonical encoding is a fixed public constant, not a placeholder that decodes back to anything. This is by design; erasure that could be reversed by anyone with read access would not satisfy the compliance obligations it exists to satisfy. |

## 10. Legal Hold and Retention Policy

### 10.1 The pruning eligibility rule

A checkpoint batch is eligible for pruning if and only if all three of the following hold, evaluated against the reference time supplied via `--now-file` (Section 12.2):

1. The owning stream is not under whole-stream legal hold (`streams.legal_hold = 0`).
2. Every event still present in that batch's `seq` range satisfies `ts <= now - retention_days * 86400` — that is, every surviving event in the batch is at least `retention_days` days old as of `now`, with the boundary **inclusive**: an event whose age is exactly equal to the retention window, to the second, counts as expired. It does not need to be one second past the window; reaching it is sufficient.
3. No event still present in that batch has `legal_hold = 1`.

All three conditions are evaluated per batch, and all three must hold for every single event currently present in that batch's range — not most of them, not all but one. The next four subsections work through why each of these design choices resolves the way it does, and Section 10.6 gives the exact per-batch decision procedure `compact` follows.

### 10.2 Whole-stream legal hold

`streams.legal_hold = 1` exempts every batch belonging to that stream from pruning, unconditionally, regardless of any individual event's age or per-event `legal_hold` value, and regardless of whether the batch in question would otherwise have been eligible many times over. This is the coarsest-grained protection ChainAudit offers, and it exists for the situation where an entire stream — not a specific subset of events within it — has become relevant to litigation, regulatory inquiry, or some other preservation obligation broad enough that itemizing which individual events are in scope would be both impractical and risky (missing even one event that should have been tagged individually defeats the purpose of a hold; a whole-stream flag cannot be under-scoped by a tagging mistake in the same way). See Section 11's sibling discussion in the changelog (2024-09-23 entry) for the specific operational experience that motivated adding this as a distinct, coarser mechanism alongside the pre-existing per-event flag.

### 10.3 Per-event legal hold and the retention comparison

Per-event `legal_hold = 1` protects a single event's containing batch from pruning, with the same unconditional force as whole-stream hold, just scoped to whichever batch that one event happens to sit in. Because pruning is strictly whole-batch (Section 10.4), a single held event anywhere in a batch protects every other event in that same batch too, whether or not those other events are individually held or even individually expired.

The age comparison itself, `ts <= now - retention_days * 86400`, deserves a fully worked numeric example, since off-by-one errors around inclusive/exclusive boundaries are exactly the kind of mistake that's easy to make and hard to notice in testing. Take `example-stream-001` (`retention_days = 90`) and a reference time of `2024-09-15T00:00:00Z` (unix `1726358400`), supplied via `--now-file`:

```
threshold = now - retention_days * 86400
          = 1726358400 - (90 * 86400)
          = 1726358400 - 7776000
          = 1718582400   (2024-06-17T00:00:00Z)
```

An event is expired if `ts <= 1718582400`. `example-stream-001`'s first checkpoint batch (`seq 0`–`3`, Section 5.6) has its latest event at `seq 3`, `ts = 1718180100` (`2024-06-12T08:15:00Z`) — before the threshold, so expired. Its second checkpoint batch (`seq 4`–`7`, Section 6.3) has its earliest event at `seq 4`, `ts = 1718841600` (`2024-06-20T00:00:00Z`) — after the threshold, so not expired, and therefore (condition 2 alone, independent of the `legal_hold = 1` already present on `seq 7` from Section 4.8) not yet eligible for pruning at this reference time.

At the exact boundary: an event with `ts = 1718582400` (precisely equal to the threshold) is expired (`1718582400 <= 1718582400` is true). An event just one second younger, `ts = 1718582401`, is not expired (`1718582401 <= 1718582400` is false). There is no grace period and no rounding to whole days on either side of this comparison — it is exact-second arithmetic against a reference time that is itself supplied to exact-second precision.

### 10.4 Whole-batch-only pruning

Pruning never deletes part of a checkpoint batch. If even a single event within a checkpointed batch's `seq` range is not yet expired, or is under per-event legal hold, the **entire batch** is retained — every row in it, including the ones that individually would have qualified for deletion many times over. There is no partial deletion within a batch, and this is a structural consequence, not merely a policy preference: a checkpoint's signed `merkle_root` (Section 5, Section 7) covers the whole batch as a single cryptographic unit. A partially-deleted batch could never again be structurally re-verified — there would be no way to recompute a Merkle root over "some of the original leaves, we're not telling you which ones are missing," and the whole point of checkpointing a batch before its rows age out is to preserve the ability to prove the batch's integrity even after its raw rows are gone (Section 6.4). Partial deletion would destroy that ability while looking, superficially, like it had preserved most of it.

**Worked example.** A checkpoint batch of 50 events, all otherwise identical in relevance: 49 of them are years past their retention window, unambiguously expired many times over. The 50th was placed under per-event legal hold yesterday. The correct behavior is to retain all 50 rows — not 49, not "49 now and revisit the 50th once its hold lifts." The single held event blocks pruning for the entire batch it sits in, for as long as the hold remains in place, no matter how overdue the other 49 are. This is not a compromise or an approximation; it is the only outcome consistent with treating the checkpointed batch as the atomic unit of pruning that Section 10 (and the checkpoint's own signed Merkle root) require it to be.

### 10.5 Mechanics: what `compact` actually executes

For each stream, `compact` walks its checkpoints in ascending `batch_index` order, and for each one whose `events` rows are still fully present (Section 3.5.5), evaluates the three conditions in Section 10.1 against that batch's currently-present rows. For each batch found eligible, `compact` issues exactly one SQL statement:

```sql
DELETE FROM events WHERE stream_id = ? AND seq BETWEEN ? AND ?
```

using that checkpoint's `start_seq` and `end_seq`, wrapped in its own transaction (Section 2.4) — so a crash or interruption between two batches' deletions leaves the database in a state consistent with having successfully processed some prefix of the eligible batches, never a state with a half-deleted batch. No other table is touched. The checkpoint row itself survives, unmodified, forever (Section 3.4, Section 3.6) — pruning removes the raw evidentiary rows while leaving the durable, signed summary of them fully intact, which is the entire mechanism by which `chain_tip_hash` survives pruning unchanged (Section 6.4).

### 10.6 Idempotency

Running `compact` twice against the same database with the same `--now-file` value must produce identical, idempotent results on the second run: any batch already pruned by the first run has zero `events` rows present for its `seq` range, fails the "fully present" precondition that gates eligibility evaluation in the first place (Section 3.5.5), and is simply skipped — not re-evaluated, not re-counted in `batches_pruned`, and not treated as an error. `compact_manifest.json`'s `batches_pruned` array (Section 13.2) reflects only batches newly pruned *by this specific run*; on a fully idempotent re-run where every eligible batch was already pruned previously, `batches_pruned` is an empty array, not a repeat of what a prior run already reported. `batches_retained` continues to list every batch that was *considered* — meaning every batch whose rows are still fully present — and found ineligible this run, so a batch's absence from both `batches_pruned` and `batches_retained` on a given run specifically indicates it was already fully pruned before this run started, distinguishing "nothing to do here, already handled" from "we looked at this and decided to keep it."

This idempotency is what makes it safe to run `compact` on a recurring schedule against the same database without tracking external state about what a previous run already did — the database itself, specifically the presence or absence of `events` rows for a given checkpoint's range, is the only state that matters, and it is self-describing on every run.

### 10.7 The uncheckpointed tail can never be pruned

Events beyond the last full checkpointed batch — the uncheckpointed tail, introduced in Section 1.1 and Section 3.4 — are never eligible for pruning, regardless of how old they are, regardless of legal hold status, regardless of anything else. This is not a policy choice that could in principle be relaxed; it is a direct consequence of Section 10.4: pruning requires a checkpoint's signed Merkle root to stand in for the deleted raw rows, and the tail, by definition, has no checkpoint covering it yet. Deleting tail events would permanently and irrecoverably destroy the only evidence that they ever existed, with no signed structure left behind to attest to what was lost — exactly the failure mode checkpointing exists to prevent. If a stream's ingestion volume is low enough, or its `checkpoint_interval` large enough, that events sit in the tail for a very long time (well past what would otherwise be their retention window once checkpointed), that is an expected, if perhaps operationally undesirable, consequence of that stream's specific configuration — the fix, if one is wanted, is operational (adjust checkpointing cadence for future streams, per Section 3.2.2's note that `checkpoint_interval` itself cannot be changed on an existing stream), not something `compact` can or should route around by pruning uncheckpointed data.

### 10.8 `retention_days = 0` is valid

A stream configured with `retention_days = 0` is not an error condition and is not rejected by `compact`. Its threshold computation, `now - 0 * 86400 = now`, means any event with `ts <= now` is immediately expired the moment `now` reaches or passes its timestamp — in practice, essentially immediately after ingestion, since `ts` values are assigned at or before the moment of ingestion and `now` (the `--now-file` reference) is normally close to the actual current time. This is an aggressive but entirely legitimate configuration for a stream whose events have no retention requirement beyond having been checkpointed at all — condition 2 in Section 10.1 becomes close to a no-op, and pruning eligibility for such a stream reduces almost entirely to conditions 1 and 3 (no whole-stream hold, no per-event hold on any surviving row in the batch).

### 10.9 `now` is supplied, never read from the system clock

`compact` never consults the system's wall-clock time for any retention decision. The reference time is always read from the file named by `--now-file`, a single decimal unix timestamp (Section 12.2). This is what makes `compact`'s output reproducible: run twice against an unchanged database with the same `--now-file` content, `compact` produces the identical manifest (modulo the idempotency behavior in Section 10.6, which itself is exactly reproducible). A `--now-file` value need not correspond to the actual present moment — a value "in the past" relative to some or all events in the database is not an error, and simply means fewer (or zero) batches are currently eligible under that reference time; this is a legitimate way to ask "what would compaction have done as of an earlier point," for rehearsal, audit reconstruction, or review purposes, without needing to wait for real time to pass.

### 10.10 Edge cases

| Case | Behavior |
|---|---|
| Batch with 49 of 50 events expired, 1 under fresh legal hold | Entire batch of 50 retained. See Section 10.4's worked example. |
| Batch already fully pruned by a prior run | Skipped on subsequent runs; not re-counted in `batches_pruned`, not listed in `batches_retained` either (Section 10.6). |
| Batch with some but not all rows present (partial-batch anomaly) | Not producible by a correctly operating `compact` (Section 3.5.5); `compact` does not attempt to evaluate or prune such a batch, since the "fully present" precondition fails, and this state is instead a `verify`-side structural-anomaly finding (`tampered_merkle_root`), not something `compact` tries to resolve or clean up. |
| Uncheckpointed tail events, however old | Never eligible, unconditionally. See Section 10.7. |
| `retention_days = 0` | Valid; near-immediate eligibility once checkpointed. See Section 10.8. |
| `--now-file` value in the past relative to most events | Valid; fewer or zero batches eligible. Not an error. See Section 10.9. |
| Whole-stream legal hold cleared after having blocked pruning for a long time | On the next `compact` run, every otherwise-eligible batch (subject to conditions 2 and 3 independently) becomes prunable in that single run — there is no additional cooldown or staged rollout of pruning after a hold lifts. |
| Per-event legal hold cleared on the one event that was blocking an otherwise fully-expired batch | Same as above, scoped to that one batch: it becomes eligible on the next run once conditions 1–3 all hold. |
| A stream with zero checkpoints | Nothing to prune — `compact` has no full batches to consider for that stream at all; its `batches_pruned` and `batches_retained` arrays are both empty. The uncheckpointed tail is untouched regardless of age, per Section 10.7. |
| A stream under whole-stream legal hold with zero checkpoints | Same as above — the hold is moot in this specific case, since there is nothing checkpointed to protect yet, but it remains correctly recorded and will take effect the moment a first checkpoint exists and ages toward eligibility. |

### 10.11 Worked example: a batch's full lifecycle from ingestion to pruning

Pulling every rule in this section together into a single timeline, using `example-stream-001`'s first checkpoint batch (`seq 0`–`3`, `retention_days = 90`) as the running example one more time:

- **2024-05-15 through 2024-06-12.** Events `seq 0` through `seq 3` are ingested (Section 4.5, Section 4.6's worked examples). At this point there is no checkpoint yet; these four events sit in the uncheckpointed tail, content-checkable but entirely unprunable regardless of how old they later become (Section 10.7).
- **shortly after 2024-06-12 (the ingest pipeline's own cadence, out of this document's scope).** The batch reaches `checkpoint_interval = 4` events and is checkpointed: `merkle_root = 48fe1a47...f2806` computed and signed (Section 5.6, Section 7.2). From this point, the batch is structurally provable independent of the raw rows, but the raw rows are still present and still what `compact` would need to delete to prune it.
- **any time before 2024-09-10T08:15:00Z (exactly `retention_days = 90` — 7,776,000 seconds — after the batch's youngest event, `seq 3` at `2024-06-12T08:15:00Z`).** Running `compact` with a `--now-file` reference time before this instant leaves the batch retained — condition 2 of Section 10.1 fails, since at least one event (`seq 3`, the youngest) has not yet aged past the retention window, regardless of what condition 1 or 3 would say.
- **at any point during this window, if the batch's whole-stream or per-event legal hold had hypothetically been set and then lifted.** Section 10.10's row on holds lifting applies: the moment all three conditions hold simultaneously, the batch becomes eligible on the very next `compact` run, with no additional delay.
- **on or after 2024-09-10T08:15:00Z (using this batch's exact youngest-event boundary; Section 10.3's own worked example used a slightly later illustrative `now` of 2024-09-15T00:00:00Z for round numbers, comfortably past this boundary), assuming no hold was ever placed.** All three conditions hold. The next `compact` run prunes the batch: `DELETE FROM events WHERE stream_id = 'example-stream-001' AND seq BETWEEN 0 AND 3` (Section 10.5), reported as `batches_pruned: [0]`, `events_deleted: 4` in that run's manifest entry (Section 13.2's worked example shows exactly this, using a `now` of `2024-09-15T00:00:00Z`).
- **every moment after that, forever.** The batch's four raw rows are gone. `event_count` for the stream reflects their absence. `checkpoint_count` does not change — the checkpoint row persists permanently (Section 3.4). `chain_tip_hash` for the stream is, and remains, exactly what it was before pruning (Section 6.4) — this is the one value in the entire timeline above that a reader could correctly predict at the very first bullet point and never need to revise, no matter what happens to the raw rows afterward.

This is also, not coincidentally, the same batch used as the running `compact_manifest.json` worked example in Section 13.2 — the JSON shown there is this timeline's final two bullet points, expressed in the tool's actual output format.

## 11. Schema Versioning and the v1 → v2 Migration

### 11.1 Why v2 exists

The v1 canonical encoding (Section 4.3) hashes `version`, `stream_id`, `seq`, `ts`, `event_type`, and the payload fields — but not `legal_hold`. This was not an oversight so much as a reflection of what the encoding format was originally designed to protect: at the time v1 shipped, `legal_hold` was a pruning-eligibility flag, consumed by retention logic, and nobody had yet examined it through the lens of "is this specific piece of metadata itself something whose integrity needs to be independently provable." The gap that realization exposed is straightforward once stated: because `legal_hold` was not part of the hashed encoding for v1 events, an event's `leaf_hash` does not change when its `legal_hold` flag changes. Someone with direct database write access to a v1-encoded event could flip `events.legal_hold` from `1` to `0` — silently lifting a legal hold that should have been protecting that event's batch from pruning — without that change being detectable by any content check `verify` performs, because the content check only ever notices changes to fields that are actually part of the hashed bytes.

This is a materially different kind of gap from an ordinary data-integrity concern: `legal_hold` is itself a compliance-and-legal control, and an undetectable way to defeat it silently undermines the retention protections Section 10 describes, independent of anything going wrong with the payload or any other field. v2 exists specifically to close this gap by folding `legal_hold` into the hashed encoding, so that from the moment an event is v2-encoded onward, tampering with its legal-hold status is exactly as detectable as tampering with its payload, its timestamp, or any other hashed field. See the 2024-07-29 and 2024-08-12 changelog entries for the full history of how this was raised, by whom, and how the design settled on a per-event migration boundary rather than some other mechanism.

### 11.2 The migration mechanism: `migrated_at`

Migrating a stream from v1 to v2 means setting `streams.migrated_at` from `NULL` to a specific unix-seconds timestamp, exactly once. From that point forward, every *newly ingested* event in that stream is compared against `migrated_at`: events timestamped at or after it encode as v2 (with the trailing `legal_hold` byte, Section 4.3); events timestamped before it — including any event ingested after the migration operation itself, if for some reason its `ts` were backdated to before `migrated_at` — encode as v1. This is the same rule stated formally in Section 4.2; this section covers the operational and historical *why* behind it, not a restatement of the byte-level mechanics already covered there.

Critically, and worth restating in the strongest possible terms because it is easy to assume otherwise: **migration never re-encodes, backfills, or touches any already-ingested event.** Every event ingested before the migration operation keeps whatever `leaf_hash` it already had, computed under the v1 rule, forever — exactly as Section 3.3.3's "computed once, never recomputed in place" invariant requires. A stream's migration is a statement about the future, not a rewrite of its past: "starting from this timestamp, new events in this stream will be v2-encoded." It says nothing about, and changes nothing for, events that already exist.

### 11.3 `migrated_at` is immutable once set

`streams.migrated_at` follows the same immutability rule as `streams.checkpoint_interval` (Section 3.2.2), for a closely related reason. Version selection (Section 4.2) is not a value stored anywhere per-event — it is derived, on demand, every time it's needed, by comparing the event's `ts` against the *current* value of `streams.migrated_at`. This is exactly what makes mixed-version streams possible without a backfill step (Section 4.2), but it also means the derivation has no memory of what `migrated_at` was at the moment any specific event was actually ingested — it only ever sees whatever value is on the `streams` row right now.

This has a direct consequence: **if `migrated_at` were changed after events have already been ingested — moved earlier, moved later, or reset back to `NULL` — every content-check recomputation from that point forward would derive versions for existing events using the new value, not the value that was actually in effect when those events were originally hashed.** Any event whose derived version flips as a result (an event that was v1 at ingestion because its `ts` was before the *old* `migrated_at`, but which now falls after a *new*, earlier `migrated_at`, would suddenly be expected to be v2-shaped — a different length, a trailing `legal_hold` byte that was never part of what was actually hashed at ingestion) would fail its content check permanently, indistinguishable from genuine tampering, even though nothing about the event's own stored fields ever changed. The bug would be entirely in the mismatch between "what version was used to compute the stored `leaf_hash`" and "what version the current `migrated_at` value causes `verify` to expect" — a self-inflicted, systemic false-positive corruption signal affecting every event on the wrong side of the changed boundary, not a one-row anomaly.

For this reason, `migrated_at`, once set to a non-`NULL` value, must never be changed again — not adjusted to a different timestamp, and not reset to `NULL`. If a stream's migration was configured incorrectly, current tooling's answer, same as for `checkpoint_interval` (Section 3.2.2), is to treat it as a new-stream decision going forward rather than to mutate the existing stream's row; there is no supported in-place correction mechanism, precisely because the "correction" would silently invalidate the hash-derivation assumptions every already-ingested event's stored `leaf_hash` depends on.

### 11.4 Worked example, referenced

Section 5.6 already works through the concrete case this section motivates: `example-stream-001`, migrated at `2024-06-01T00:00:00Z`, with a first checkpoint batch (`seq 0`–`3`) containing two v1 events (`seq 0`, `seq 1`, timestamped in mid-May, before migration) and two v2 events (`seq 2`, `seq 3`, timestamped in mid-June, after migration) — and Section 5.6 shows explicitly that Merkle construction folds all four leaf hashes with no version-aware branching whatsoever. That worked example *is* this section's worked example; it is not repeated here, only cross-referenced, because the byte-level mechanics are identical regardless of which section motivates looking at them — Section 4 for "how does the encoding differ," this section for "why does the encoding differ at all."

### 11.5 Streams that never migrate

A stream whose `migrated_at` remains `NULL` indefinitely is not a stream in a degraded or incomplete state — it is simply a stream that has not been (and may never be) migrated, and every event in it, past and future, is v1-encoded for as long as that remains true. `example-stream-002` in this document's worked examples (Section 5.2) is exactly this case. Migration is not automatic, is not required by any check `verify` performs (a pure-v1 stream with no `legal_hold`-tampering exposure concerns is not reported as degraded, deficient, or any special status relative to a migrated one — v1 is a fully supported, fully legitimate, permanent encoding, not a deprecated one awaiting cleanup), and is a decision made per stream by whoever owns that stream's data, typically prioritized for streams where `legal_hold` integrity specifically matters most (streams known to be subject to frequent or high-stakes legal holds) rather than applied uniformly across every stream in the system on some fixed schedule. Low-volume streams, streams slated for eventual decommissioning, and streams whose events are not realistically subject to legal hold at all are common examples of streams that may reasonably stay on v1 permanently, by deliberate choice rather than neglect.

### 11.6 Operational process (out of scope, mentioned for context)

The actual mechanics of deciding to migrate a specific stream, choosing its `migrated_at` value, and executing the single `UPDATE streams SET migrated_at = ? WHERE stream_id = ? AND migrated_at IS NULL` that performs the migration are owned by the audit-ingest pipeline's own tooling and operational process, not by the `chainaudit` CLI — neither `verify` nor `compact` ever writes to `streams.migrated_at` under any circumstance. This document describes the migration's effect on encoding and hashing precisely because that effect is exactly what `verify` and `compact` must interpret correctly; it does not describe the upstream decision process or tooling that triggers a migration, which is out of scope here in the same way ingestion and checkpoint creation are (Section 1.1).

### 11.7 Edge cases

| Case | Behavior |
|---|---|
| Event `ts` exactly equal to `migrated_at` | v2. The comparison is `>=`, inclusive on the v2 side (Section 4.2). |
| Event `ts` one second before `migrated_at` | v1. |
| `migrated_at` set to a timestamp in the future relative to all currently-ingested events | Valid. Every event ingested so far remains v1 (their `ts` values are all necessarily before this future `migrated_at`); the stream will begin producing v2 events once ingestion reaches that timestamp. Not an error, and a legitimate way to schedule a migration in advance. |
| A batch containing only v1 events, immediately followed by a batch containing only v2 events, with no batch straddling the boundary | Fully possible, if the migration boundary happens to fall exactly on a checkpoint boundary — Section 4.2 and Section 5.6's straddling example describe the general case, not a requirement that every migration must straddle some batch. |
| `migrated_at` changed after being set | Not supported; produces systemic, permanent, false content-check failures for every event whose derived version flips as a result. See Section 11.3. Treated as an operator error in upstream tooling, not something `chainaudit verify` can detect as a distinct condition or repair — it manifests simply as a wave of `tampered_event` findings with no evidence of any actual payload tampering. |
| A stream migrates, then later needs `legal_hold` tamper-evidence extended retroactively to its pre-migration events | Not possible without changing those events' `leaf_hash`, which would invalidate every checkpoint that already covers them (Section 3.3.3, Section 6.4). There is no retroactive-hardening mechanism; v1 events, once ingested, remain v1 forever, with whatever tamper-evidence coverage v1 provides (everything except `legal_hold` itself) for their entire lifetime in the system. |

## 12. CLI Reference

### 12.1 `chainaudit verify`

```
chainaudit verify --db <path> --out <path> [--kms-addr http://127.0.0.1:8500]
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--db` | Yes | — | Path to the SQLite database file to verify. Opened read-only (Section 2.5). |
| `--out` | Yes | — | Path to write `verify_report.json` (Section 13.1) to. Overwritten if it already exists. Parent directory must already exist; `verify` does not create directories. |
| `--kms-addr` | No | `http://127.0.0.1:8500` | Base URL of the Key Management service (Section 8). Point this at `cmd/mockkms` (Section 2.3) for local development or staging rehearsal. |

`verify` iterates every row in `streams`, sorted by `stream_id` ascending (the same ordering used for the `chain_tip_hash_overall` fold, Section 6.6 — this is not a coincidence; both the iteration order and the fold order exist to make output deterministic and reproducible run over run against an unchanged database), and for each stream:

1. Walks every currently-present `events` row for that stream, in ascending `seq` order, recomputing `LeafHash` from each row's current column state and comparing against the stored `leaf_hash` (Section 4.4). The lowest `seq` where this comparison fails becomes `first_bad_seq`.
2. Walks every `checkpoints` row for that stream, in ascending `batch_index` order. For a batch whose `events` rows are fully present, recomputes the Merkle root (Section 5) from current `leaf_hash` values and compares against stored `merkle_root`; for a batch whose `events` rows are fully absent, skips this recomputation entirely (Section 5.7, Section 10.6); for a batch with a partial row count, treats it as a structural anomaly (Section 3.5.5). The lowest `batch_index` where a structural check is attempted and fails becomes a candidate for `first_bad_batch`.
3. For every distinct `key_id` referenced by that stream's checkpoints, resolves key material against the Key Management service (Section 8), and for each checkpoint whose key resolved successfully, recomputes and compares its `signature` (Section 7). A mismatch against an active key is also a candidate for `first_bad_batch`; a `410` or service error is not (Section 8.7).
4. Applies the reason-precedence rule (Section 8.7) to determine the stream's single `status` and `reason`.
5. Populates `event_count` (current row count) and `checkpoint_count` (current `checkpoints` row count) directly from table state.

`verify` never modifies the database under any circumstance, including when it finds corruption (Section 2.5). Its only effect is writing `--out`.

### 12.2 `chainaudit compact`

```
chainaudit compact --db <path> --out <path> --now-file <path>
```

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--db` | Yes | — | Path to the SQLite database file to compact. Opened read-write. |
| `--out` | Yes | — | Path to write `compact_manifest.json` (Section 13.2) to. Overwritten if it already exists. |
| `--now-file` | Yes | — | Path to a file containing a single decimal unix timestamp (ASCII, no surrounding whitespace expected, trailing newline tolerated), used as `now` in every retention computation for this run (Section 10.9). |

`compact` never reads the system clock for retention purposes. This is deliberate — see Section 10.9 for the full rationale — and is why `--now-file` is a required flag with no default: there is no "just use the current time" fallback, because an operator forgetting to think about what reference time a compaction run should use is exactly the kind of silent, easy-to-miss mistake this design forces into the open. A typical operational pattern is to write the current time into a small file immediately before invoking `compact`, ensuring the reference time used matches the operator's actual intent at the moment they decided to run it, and keeping that file around alongside the resulting manifest as a record of what reference time produced it.

`compact` iterates every row in `streams`, sorted by `stream_id` ascending (same ordering convention as `verify`, for the same determinism reasons), and for each stream walks its checkpoints in ascending `batch_index` order, applying the procedure in Section 10.5 and Section 10.6. Its only write to the database is the narrow `DELETE` described there; it never touches `streams` or `checkpoints`, and never calls the Key Management service (Section 2.6, Section 8.1).

### 12.3 Exit codes

| Exit code | Meaning |
|---|---|
| `0` | The subcommand ran to completion and wrote its output file. This includes runs where one or more streams were found `corrupt` or `legacy_unverifiable` — finding corruption is a successful `verify` run reporting bad news, not a failed run. Exit code `0` reflects "the tool did its job," not "everything it found was fine." |
| `1` | The subcommand could not complete — a missing or unreadable `--db` file, a `--db` file missing the expected schema (Section 2.1), an unwritable `--out` path, a malformed `--now-file` (`compact` only), or an unrecoverable error partway through (for `compact`, this can leave some batches pruned and others not yet evaluated — Section 2.4's per-batch transaction boundary means whatever was committed stays committed, but the manifest is not written if the run did not complete, so an operator should re-run rather than assume partial progress was recorded anywhere durable). |
| `2` | Invalid command-line invocation — missing a required flag, an unrecognized flag, or a subcommand name that isn't `verify` or `compact`. |

Consult the JSON output file itself, not the process exit code, to learn whether any stream was found `corrupt` or `legacy_unverifiable` — that information exists only in `--out`, never encoded in the exit code, again because "the tool ran successfully and told you the truth" and "the truth was bad" are different facts and only the first one belongs in an exit code.

### 12.4 Logging

Both subcommands log operational detail — which stream is currently being processed, KMS retry attempts and their outcomes (Section 8.4), transaction commit/rollback events for `compact` — to stderr as unstructured, human-readable text. Stdout is reserved for nothing in particular (neither subcommand writes report content to stdout; the report always goes to the file named by `--out`), so stdout can be safely ignored or redirected without losing any part of the actual output. Log verbosity is not currently configurable via a flag; operators needing more or less detail should file a request rather than assume an undocumented environment variable controls it.

### 12.5 Examples

Verify a production database, writing the report to a timestamped path, using the default KMS address:

```
chainaudit verify --db /var/lib/chainaudit/prod.sqlite --out /var/log/chainaudit/verify-2025-05-27.json
```

Verify against a staging KMS instance running on a non-default port:

```
chainaudit verify --db /var/lib/chainaudit/staging.sqlite --out /tmp/verify-staging.json --kms-addr http://127.0.0.1:9500
```

Compact using a reference time captured just before the run:

```
date +%s > /tmp/compact-now.txt
chainaudit compact --db /var/lib/chainaudit/prod.sqlite --out /var/log/chainaudit/compact-2025-05-27.json --now-file /tmp/compact-now.txt
```

Rehearse what compaction would have done as of an earlier date, without mutating a live database (point `--db` at a copy):

```
echo 1704067200 > /tmp/rehearsal-now.txt   # 2024-01-01T00:00:00Z
cp /var/lib/chainaudit/prod.sqlite /tmp/prod-copy.sqlite
chainaudit compact --db /tmp/prod-copy.sqlite --out /tmp/rehearsal-manifest.json --now-file /tmp/rehearsal-now.txt
```

The standard operational pairing — confirm integrity, then prune, then confirm the tip hashes agree (Section 6.4) — chains `verify`, `compact`, and `verify` again:

```
chainaudit verify  --db prod.sqlite --out before.json
date +%s > now.txt
chainaudit compact --db prod.sqlite --out manifest.json --now-file now.txt
chainaudit verify  --db prod.sqlite --out after.json
# for every stream, before.json's chain_tip_hash == manifest.json's chain_tip_hash == after.json's chain_tip_hash
```

### 12.6 Configuration surface

Both subcommands are configured exclusively through the command-line flags documented in Section 12.1 and Section 12.2. There is no configuration file, and no environment variable alters either subcommand's behavior — `--kms-addr` has a default (`http://127.0.0.1:8500`) but every other required input (`--db`, `--out`, and `compact`'s `--now-file`) must be supplied explicitly on every invocation, with no fallback to an implicit or previously-remembered value. This is a deliberate continuation of the same philosophy behind `--now-file` having no wall-clock fallback (Section 10.9): an audit and retention tool's behavior on a given run should be fully reconstructable from the command line that invoked it, without needing to also know what environment variables happened to be set, or what a configuration file elsewhere on the host happened to contain at the time. Operators wrapping `chainaudit` in their own scripts or scheduling tooling are encouraged to log the exact invocation (all flags, resolved to absolute paths) alongside the run's output, since that invocation line is a complete, sufficient record of what governed that specific run's behavior.

### 12.7 Signals and interruption

Neither subcommand installs custom handling for `SIGINT` or `SIGTERM` beyond what the Go runtime and the underlying SQLite driver do by default: an interrupt during `verify` simply stops the process, discarding whatever partial report state was being accumulated in memory (nothing is written to `--out` unless the run reaches completion, Section 2.5); an interrupt during `compact` stops the process similarly, but because each batch's deletion is wrapped in its own transaction (Section 2.4, Section 10.5), whatever batch was fully committed at the moment of interruption stays committed, and whatever batch was mid-transaction at that moment is rolled back by SQLite's own transaction semantics rather than left in an inconsistent state. In both cases, the correct recovery action is simply to re-run the interrupted subcommand — `verify` because it has no state to reconcile in the first place (Section 2.5), and `compact` because of the idempotency guarantee in Section 10.6, which was designed with exactly this kind of interruption in mind, not only with routine rescheduling. There is no `--resume` flag and none is needed; idempotent re-invocation is the resume mechanism.

## 13. JSON Output Schema Appendix

### 13.1 `verify_report.json`

#### Top level

| Field | Type | Meaning |
|---|---|---|
| `db_path` | string | The value passed to `--db` for this run, recorded verbatim (not resolved to an absolute path or canonicalized). |
| `chain_tip_hash_overall` | string (64 hex chars) | The fold of every stream's `chain_tip_hash`, sorted by `stream_id` ascending. Construction: Section 6.6. |
| `streams` | array of objects | One entry per row in `streams`, sorted by `stream_id` ascending. Empty array for a database with no streams. |

#### Per-stream entry

| Field | Type | Meaning |
|---|---|---|
| `stream_id` | string | Verbatim from `streams.stream_id`. |
| `status` | string enum | One of `"ok"`, `"legacy_unverifiable"`, `"corrupt"`. See Section 8.7 for the precedence rule that determines this. |
| `event_count` | int | Current row count in `events` for this stream — reflects post-compaction reality when `verify` is run after `compact` has pruned some batches (Section 3.4). |
| `checkpoint_count` | int | Current row count in `checkpoints` for this stream. Never changes as a result of any `compact` run (Section 3.4). |
| `chain_tip_hash` | string (64 hex chars) | This stream's tip-chain fold (Section 6.2, Section 6.3). `Genesis(stream_id)` if the stream has zero checkpoints (Section 6.5). |
| `first_bad_seq` | int or `null` | Set only when a content check fails somewhere in this stream (checkpointed or in the uncheckpointed tail); the lowest such `seq`. `null` if every content check passed. |
| `first_bad_batch` | int or `null` | Set only when a structural check or an active-key signature check fails for some checkpoint in this stream; the lowest such `batch_index`. `null` if no such failure occurred — including when the only KMS-related finding is a `410` or a service error (Section 8.5, Section 8.7). |
| `reason` | string enum or `null` | `null`, or one of `"tampered_event"`, `"tampered_merkle_root"`, `"tampered_checkpoint_signature"`, `"revoked_key"`, `"kms_unavailable"`. Precedence when multiple apply: Section 8.7. |
| `revoked_key_ids` | array of strings | Every distinct `key_id` that returned `410` while verifying this stream's checkpoints, in ascending lexical order. Always present as an array — `[]`, not `null`, when there are none. |

#### `status` / `reason` quick-reference matrix

Every reachable combination of `status` and `reason`, collected as a single lookup table — a different presentation of the same precedence rule from Section 8.7, useful for scanning rather than reading in prose:

| `status` | `reason` | `first_bad_seq` | `first_bad_batch` | `revoked_key_ids` | Meaning |
|---|---|---|---|---|---|
| `ok` | `null` | `null` | `null` | `[]` | Every check that could be performed, was, and passed. |
| `legacy_unverifiable` | `revoked_key` | `null` | `null` | non-empty | At least one checkpoint's key has been rotated out; nothing else found wrong. |
| `legacy_unverifiable` | `kms_unavailable` | `null` | `null` | `[]` | At least one checkpoint's signature could not be checked due to a transient or service-level KMS problem; nothing else found wrong. |
| `corrupt` | `tampered_event` | set | `null` or set | `[]` or non-empty | A content-check failure exists somewhere; may coexist with structural or KMS findings, but this reason wins precedence regardless. |
| `corrupt` | `tampered_merkle_root` | `null` | set | `[]` or non-empty | A structural mismatch on an intact batch (including the partial-batch and non-contiguous-`batch_index` anomalies); no content-check failure found. |
| `corrupt` | `tampered_checkpoint_signature` | `null` | set | `[]` | An active key produced a definitive, negative signature check; no content or structural failure found. |

Every row combination not listed here — for instance, `status = "ok"` with a non-null `reason`, or `status = "corrupt"` with `reason = "revoked_key"` — is not producible by `verify` and should be treated as a bug in whatever produced it if ever observed.

#### Worked example

Using the two streams built up across Sections 4 through 7 (`example-stream-001`, `example-stream-002`), in their state before any pruning has occurred — eight events and two checkpoints for the first, five events and one checkpoint for the second, nothing tampered, every key active:

```json
{
  "db_path": "/var/lib/chainaudit/prod.sqlite",
  "chain_tip_hash_overall": "17ca833b2e1b96ac63cd43d2055949db0f82512cadfb447e9c511ed567b0f8ab",
  "streams": [
    {
      "stream_id": "example-stream-001",
      "status": "ok",
      "event_count": 8,
      "checkpoint_count": 2,
      "chain_tip_hash": "84e97146283735253c14119f3fe742217b445736257777b5ecae2dbc25f52acc",
      "first_bad_seq": null,
      "first_bad_batch": null,
      "reason": null,
      "revoked_key_ids": []
    },
    {
      "stream_id": "example-stream-002",
      "status": "ok",
      "event_count": 5,
      "checkpoint_count": 1,
      "chain_tip_hash": "34fd4312f16061e9e0c053e2ee251be0bd9601cb74021f61d047e9c9652c1f93",
      "first_bad_seq": null,
      "first_bad_batch": null,
      "reason": null,
      "revoked_key_ids": []
    }
  ]
}
```

Note `chain_tip_hash_overall` here is exactly the value derived by hand in Section 6.6, folding these same two streams' `chain_tip_hash` values in `stream_id` order — this JSON is not a fresh example, it is the previous six sections' worked arithmetic, expressed in the format `verify` actually emits.

#### Worked examples of the non-`ok` statuses

For illustration, four more per-stream entries, one for each non-null `reason`, showing the shape each takes (stream identifiers here are illustrative placeholders, not continuations of the running `example-stream-001`/`002` scenario above):

A content-check failure (Section 4.9's tampered-payload illustration, if it had actually been written back to storage rather than only discussed hypothetically):

```json
{
  "stream_id": "example-stream-003",
  "status": "corrupt",
  "event_count": 4,
  "checkpoint_count": 1,
  "chain_tip_hash": "9f2c...redacted-for-brevity...",
  "first_bad_seq": 2,
  "first_bad_batch": null,
  "reason": "tampered_event",
  "revoked_key_ids": []
}
```

A structural (Merkle root) failure — note `first_bad_seq` can legitimately be `null` here; nothing about the individual events' content needs to be wrong for the batch's recomputed root to disagree with what was signed (Section 9.5's erasure-driven case is one honest way this arises; a genuine attack on stored `leaf_hash` values directly, bypassing both sanctioned write paths, is another):

```json
{
  "stream_id": "example-stream-004",
  "status": "corrupt",
  "event_count": 4,
  "checkpoint_count": 1,
  "chain_tip_hash": "3ab1...redacted-for-brevity...",
  "first_bad_seq": null,
  "first_bad_batch": 0,
  "reason": "tampered_merkle_root",
  "revoked_key_ids": []
}
```

A revoked key, everything else clean (Stream P from Section 8.3.1):

```json
{
  "stream_id": "example-stream-005",
  "status": "legacy_unverifiable",
  "event_count": 4,
  "checkpoint_count": 1,
  "chain_tip_hash": "7cd0...redacted-for-brevity...",
  "first_bad_seq": null,
  "first_bad_batch": null,
  "reason": "revoked_key",
  "revoked_key_ids": ["kms-2024-06-a"]
}
```

An active key with a genuinely bad signature (Stream Q from Section 8.3.1):

```json
{
  "stream_id": "example-stream-006",
  "status": "corrupt",
  "event_count": 4,
  "checkpoint_count": 1,
  "chain_tip_hash": "b4e8...redacted-for-brevity...",
  "first_bad_seq": null,
  "first_bad_batch": 0,
  "reason": "tampered_checkpoint_signature",
  "revoked_key_ids": []
}
```

### 13.2 `compact_manifest.json`

#### Top level

| Field | Type | Meaning |
|---|---|---|
| `db_path` | string | The value passed to `--db` for this run, recorded verbatim. |
| `now` | int | Unix seconds; the reference time read from `--now-file` and used for every retention computation this run (Section 10.9). |
| `streams` | array of objects | One entry per row in `streams`, sorted by `stream_id` ascending. Empty array for a database with no streams. |

#### Per-stream entry

| Field | Type | Meaning |
|---|---|---|
| `stream_id` | string | Verbatim from `streams.stream_id`. |
| `batches_pruned` | array of int | `batch_index` values newly pruned **by this run**. Empty array on a fully idempotent re-run where every eligible batch was already pruned previously (Section 10.6). |
| `batches_retained` | array of int | `batch_index` values that were considered this run (i.e., whose `events` rows were still fully present at the start of this run) and found ineligible. Does not include batches that were already fully pruned before this run started — those are simply absent from both arrays. |
| `events_deleted` | int | Total count of `events` rows deleted for this stream by this run — equal to the sum of `checkpoint_interval` over every `batch_index` in this entry's `batches_pruned` (since pruning is always whole-batch, Section 10.4). `0` on a run that pruned nothing for this stream. |
| `chain_tip_hash` | string (64 hex chars) | This stream's tip-chain fold, computed identically to the `verify_report.json` field of the same name (Section 6.2). Must equal the corresponding `verify_report.json` value for this stream both immediately before and immediately after this run (Section 6.4). |

#### Worked example

Continuing the same two streams, now running `compact` with `--now-file` containing `1726358400` (`2024-09-15T00:00:00Z`, the reference time worked through in Section 10.3). At this reference time: `example-stream-001`'s batch 0 (`seq 0`–`3`, all four events timestamped before the 90-day threshold of `2024-06-17T00:00:00Z`, none held) is eligible and pruned; its batch 1 (`seq 4`–`7`) is not yet expired (and separately still carries a `legal_hold = 1` event at `seq 7`) and is retained. `example-stream-002`'s single batch (`seq 0`–`4`, 30-day retention, all five events timestamped in March 2024, comfortably past the `2024-08-16T00:00:00Z` threshold, none held) is eligible and pruned in its entirety:

```json
{
  "db_path": "/var/lib/chainaudit/prod.sqlite",
  "now": 1726358400,
  "streams": [
    {
      "stream_id": "example-stream-001",
      "batches_pruned": [0],
      "batches_retained": [1],
      "events_deleted": 4,
      "chain_tip_hash": "84e97146283735253c14119f3fe742217b445736257777b5ecae2dbc25f52acc"
    },
    {
      "stream_id": "example-stream-002",
      "batches_pruned": [0],
      "batches_retained": [],
      "events_deleted": 5,
      "chain_tip_hash": "34fd4312f16061e9e0c053e2ee251be0bd9601cb74021f61d047e9c9652c1f93"
    }
  ]
}
```

Both `chain_tip_hash` values here are byte-identical to the `verify_report.json` worked example in Section 13.1 above, computed while all thirteen events across both streams were still present — exactly the invariant Section 6.4 describes, now shown holding across an actual pruning run rather than only argued in the abstract. `example-stream-002` is a clean illustration of the "fully pruned down to zero surviving events" edge case from Section 6.7: `events_deleted = 5` removes every remaining row for that stream, `batches_retained` is correctly empty (there was nothing left to retain a decision about after the one batch was pruned), and `chain_tip_hash` is completely unaffected, because it was never a function of those five rows in the first place.

A second, immediate re-run of `compact` against the resulting database, with the same `--now-file` content, produces:

```json
{
  "db_path": "/var/lib/chainaudit/prod.sqlite",
  "now": 1726358400,
  "streams": [
    {
      "stream_id": "example-stream-001",
      "batches_pruned": [],
      "batches_retained": [1],
      "events_deleted": 0,
      "chain_tip_hash": "84e97146283735253c14119f3fe742217b445736257777b5ecae2dbc25f52acc"
    },
    {
      "stream_id": "example-stream-002",
      "batches_pruned": [],
      "batches_retained": [],
      "events_deleted": 0,
      "chain_tip_hash": "34fd4312f16061e9e0c053e2ee251be0bd9601cb74021f61d047e9c9652c1f93"
    }
  ]
}
```

`example-stream-001`'s batch 0 is no longer mentioned in either array (Section 10.6 — it was already pruned, so it isn't re-evaluated or re-counted), batch 1 is still correctly evaluated and still retained (its eligibility genuinely hasn't changed), and `events_deleted` correctly reports `0` — nothing new happened for this stream on this run. `example-stream-002` has no checkpoints left with any rows to consider at all, so both its arrays are empty. Both `chain_tip_hash` values are, as always, unchanged.

## 14. Operational FAQ / Troubleshooting

**Q: `verify` reported `legacy_unverifiable` for a stream I'm confident is fine. Is something wrong?**

Not necessarily, and probably not. Check the `reason` field before assuming the worst: `revoked_key` means one or more of that stream's checkpoints were signed under a key that has since been rotated out of active service, which is a routine, expected lifecycle event for a managed key, not evidence of a problem with the stream's data (Section 8.3). Check `revoked_key_ids` for which key, and cross-reference against the Key Management team's rotation schedule if you want independent confirmation that the rotation was intentional and scheduled rather than a surprise. If `reason` is instead `kms_unavailable`, see the next entry.

**Q: `verify` reported `kms_unavailable` — what should I actually do?**

First, confirm the Key Management service is reachable at all from wherever `verify` is running (`--kms-addr` pointed at the right place, network path open, service actually up) — a surprising fraction of `kms_unavailable` reports trace back to a stale or wrong `--kms-addr` value rather than an actual service outage. If the service is genuinely down or degraded, wait for it to recover and re-run `verify`; there is no persistent retry queue, so re-running the whole command is how you retry (Section 8.5). If it keeps happening against a service that looks healthy, check whether you're being rate-limited (`429`, Section 8.4) faster than your client's backoff can clear, which usually shows up in the stderr log as repeated retry attempts before the final failure.

**Q: How do I tell a routine key rotation apart from a real incident, at a glance, across a whole fleet of databases?**

Look at `reason`, not just `status`. `revoked_key` and `kms_unavailable` both report as `status = "legacy_unverifiable"`, which is intentionally the least alarming of the three status values, but only `revoked_key` is a durable, expected fact worth simply noting; `kms_unavailable` is worth investigating if it persists across re-runs, since it suggests an availability problem with the Key Management service itself rather than anything about your data. Neither should be confused with `status = "corrupt"`, which is the only status that should page anyone. See Section 8.3.1 for the full worked contrast between the two situations that can produce a superficially identical "signature couldn't be confirmed" symptom.

**Q: I added a large batch of new events to a stream, but `chain_tip_hash` in my `verify` report didn't change. Is that a bug?**

No — this is expected and is covered in depth in Section 6.5. `chain_tip_hash` only advances when a new checkpoint is cut; appending raw events does not, by itself, move it, even if you append thousands of them. Check `event_count` instead if you want to confirm the new events actually landed — it reflects the current row count and will show the increase immediately, while `chain_tip_hash` and `checkpoint_count` will only change once a full `checkpoint_interval`-sized batch has been checkpointed (a process outside `verify` and `compact`, Section 1.1).

**Q: I ran `compact`, and `event_count` dropped but `checkpoint_count` didn't. Is that a bug?**

No, that's the expected and correct signature of successful pruning (Section 3.4). `compact` only ever deletes `events` rows; it never touches `checkpoints` rows, so `checkpoint_count` for a stream is invariant across any number of `compact` runs, while `event_count` shrinks as batches age out and get pruned. If you ever see `checkpoint_count` change after a `compact` run, that would indicate something outside ChainAudit's own write path touched the `checkpoints` table directly, which is worth investigating on its own — but ordinary pruning will never cause it.

**Q: Can I run `verify` and `compact` at the same time against the same database?**

Operational practice is not to, and this document assumes exclusive access for the duration of a `compact` run (Section 2.4). SQLite's own locking will generally prevent outright corruption from concurrent access, but a `verify` run that reads a database mid-`compact` may observe a batch in the process of being deleted and report on a state that never existed as a stable snapshot — not dangerous, but confusing enough to avoid deliberately. Run them sequentially, or against a snapshot taken while `compact` is not running.

**Q: What happens if `compact` crashes or is killed partway through a run?**

Whatever batches had already been committed (Section 2.4 and Section 10.5 — each batch's deletion is its own transaction) stay pruned; whatever batches hadn't yet been evaluated remain untouched, exactly as if the run had simply stopped early. Because `compact` is idempotent (Section 10.6), the correct recovery action is simply to re-run it with the same (or a fresh) `--now-file` — it will correctly skip whatever was already pruned and pick up wherever it left off, with no manual bookkeeping required. Note, though, that the manifest for the interrupted run is not written if the process didn't reach completion, so you won't have a JSON record of exactly how far it got; the database state itself is the only durable record in that case.

**Q: A batch has 50 events, 49 of them clearly past retention, but `compact` isn't pruning it. Why?**

Check whether any single event in that batch's range still has `legal_hold = 1`, or whether the owning stream has `legal_hold = 1` at the stream level. Pruning is strictly whole-batch (Section 10.4) — a single held or unexpired event anywhere in the batch retains the entire batch, including the 49 events that are individually long overdue. This is intentional, not a defect; see the worked example in Section 10.4.

**Q: How do I find out exactly which event is blocking a batch from being pruned?**

`compact_manifest.json` itself doesn't enumerate which specific event blocked a retained batch — `batches_retained` tells you *that* a batch was considered and kept, not *why*. To find the specific blocker, query the `events` table directly for that batch's `seq` range and check for any row with `legal_hold = 1`, or any row with `ts` still greater than your retention threshold (Section 10.3's worked arithmetic shows exactly how to compute that threshold by hand). This is a deliberate scope boundary: the manifest reports pruning *outcomes*, and diagnosing a specific retention decision is a query against the live table, not a field this document's JSON schemas carry.

**Q: Can I change a stream's `checkpoint_interval` after it's already been ingesting for a while?**

No — see Section 3.2.2. Nothing at the SQLite level stops the `UPDATE`, but doing so desynchronizes the interval from every checkpoint already cut under the old value and is not a supported operation. If a stream genuinely needs a different cadence, current tooling's answer is a new `stream_id`, not a mutation of the existing one.

**Q: Same question, but for `migrated_at` — can I fix a stream's migration timestamp after the fact if it turns out to be wrong?**

No, for a closely related but distinct reason — see Section 11.3. Changing `migrated_at` after events have already been ingested under the old value causes `verify`'s version-derivation to disagree with what was actually used to compute those events' stored `leaf_hash`, producing a wave of spurious `tampered_event` findings with no actual data problem behind them. If a migration was configured incorrectly, treat it the same way as a `checkpoint_interval` mistake: it is not correctable in place.

**Q: `verify` is reporting `tampered_merkle_root` on a batch, but I know a right-to-erasure request was processed against an event in that exact batch recently. Is this a false positive I can ignore?**

Probably, but confirm rather than assume — see Section 9.5 for the full mechanism. Erasing a payload from an already-checkpointed event necessarily changes that event's `leaf_hash`, which the checkpoint's immutable, already-signed `merkle_root` can never be reconciled with again until that batch is eventually pruned. Cross-reference the checkpoint's `seq` range (from `first_bad_batch`) against the compliance team's erasure log for that time window; if it lines up with a known, authorized erasure, this is expected and will resolve itself once the batch ages into eligibility for pruning. If it doesn't line up with any known erasure, escalate it as a genuine finding — `verify`'s report can't make this distinction for you, since both situations produce an identical structural mismatch.

**Q: How do I recover a tombstoned event's original payload?**

You can't, by design (Section 9.7). The actual bytes are gone from the `payload` column, not merely hidden, and the sentinel that stands in for them in the canonical encoding is a fixed public constant — it carries no information about what was erased. If this capability is ever needed, it has to come from a system that retains the data independently of ChainAudit (and would then need its own, separate justification for why it's allowed to retain what was supposed to have been erased).

**Q: What's actually the difference between `tombstone` and `legal_hold` on an event? They both sound like "don't touch this."**

They govern different operations and are independent of each other (Section 9.4). `tombstone` records that the event's payload has been redacted for a data-erasure obligation — a one-way transition, never reversed. `legal_hold` records that the event's row is currently exempt from pruning — reversible, and unrelated to whether the payload has been redacted. An event can be tombstoned and held at the same time (its payload is gone, but the fact and timing of the event are being preserved from deletion for litigation purposes), held without being tombstoned (the common case), tombstoned without being held (also common — most erasures have nothing to do with litigation), or neither.

**Q: Does `verify` ever modify the database it's checking?**

Never, under any circumstance, including when it finds corruption (Section 2.5). It opens the database read-only at the connection level. Its only output is the JSON file at `--out`.

**Q: My `stream_id` contains non-ASCII characters (accented letters, CJK characters, emoji) and something about a length or a hash looks wrong. What should I check first?**

Confirm whatever is computing or checking the length prefix is measuring UTF-8 encoded bytes, not characters or Unicode code points (Section 3.2.1, Section 4.11). A `stream_id` with four-byte UTF-8 characters in it has a byte length considerably larger than its character count, and `stream_id_len` must reflect the byte count. This has been the root cause of at least one real client bug — see the 2025-01-06 changelog entry.

**Q: `first_bad_seq` and `first_bad_batch` are both non-null in the same report. Which one is "the" problem?**

Both are. They're populated independently, from independent checks, and are not mutually exclusive (Section 8.7). A stream can simultaneously have a tampered event somewhere in its content and a structurally-broken checkpoint somewhere else entirely — the `reason` field will name whichever finding has higher precedence (`tampered_event` outranks `tampered_merkle_root` in the fixed precedence order), but that does not mean the other field's finding isn't real or doesn't need attention. Always inspect both fields directly on a `corrupt` stream rather than assuming `reason` tells the whole story.

**Q: Why doesn't ChainAudit just retry the Key Management service forever until it gets an answer?**

Because a caller that retries indefinitely against a struggling service makes that service's problem worse for every other caller, not just itself — see the 2024-11-04 changelog entry for a concrete incident where exactly this pattern, in a different internal tool, degraded the Key Management service broadly. `verify` backs off with jitter and gives up after a bounded number of attempts, reporting `kms_unavailable` and leaving the retry decision (running `verify` again) to the operator, who has context about urgency that the tool itself doesn't.

**Q: Can I use a `verify_report.json` as evidence in an actual audit or regulatory response?**

That is exactly the use case this tool and this document are built around, but treat the report as a snapshot: it reflects the database's state and the Key Management service's state at the specific moment it was generated. A report showing `status: "ok"` for a stream is a positive statement about that stream's integrity as of that run; it says nothing about the state of the database a moment before or after. If a report needs to serve as durable evidence, retain the report file itself (and, ideally, the `--db` file's state, or a hash of it, alongside it) rather than relying on being able to regenerate an identical report later — a later `compact` run, for instance, is expected to change `event_count` while leaving `chain_tip_hash` unchanged, and reproducing a byte-identical report after any pruning has occurred should not be expected for fields that reflect current row counts.

**Q: I pointed `--db` at a file that isn't actually a ChainAudit database. What happens?**

Both subcommands fail fast — Section 2.1. ChainAudit does not attempt to create the `streams`, `events`, or `checkpoints` tables if they're missing, and does not attempt to interpret an unrelated SQLite file's schema as if it might coincidentally match. This is deliberate: a missing table on a path someone pointed a compliance tool at is much more likely to mean the wrong file was given than that a fresh install needs bootstrapping, and guessing wrong in that situation is worse than simply refusing.

**Q: My stream's `checkpoint_interval` is 137 — an arbitrary, non-round, non-power-of-two number. Is that actually supported, or just technically not rejected?**

Fully supported, not merely tolerated — there is no requirement anywhere in this system that `checkpoint_interval` be a power of two, or round, or any particular shape at all (Section 3.2). It's worth knowing, per Section 5.5, that a non-power-of-two interval is exactly what exercises the interesting (odd-count-handling) branch of the Merkle construction — which is a reason to feel *more* confident testing against such a stream, not less, not a reason to think it's an unusual or risky configuration.

**Q: Is there a way to undo a `compact` run — restore pruned events if it turns out they shouldn't have been pruned?**

No, and this is by design rather than a missing feature. Pruned rows are gone; the checkpoint that covered them remains as durable proof of what they were (their count, their `seq` range, and their collective Merkle root) but not as a means of restoring their actual content. This is exactly why the eligibility rules in Section 10 are conservative by design — every ambiguous case resolves toward retention, specifically because pruning is not reversible and the cost of pruning something that should have been kept is much higher than the cost of keeping something a little longer than strictly necessary.

**Q: Does `compact` need network access to run?**

No. Unlike `verify`, `compact` never calls the Key Management service or makes any network call at all — every input to its pruning decisions (timestamps, hold flags) comes from the local database and the local `--now-file` (Section 2.6, Section 12.2). A `compact` run can be executed entirely offline.

**Q: I ran `compact` twice with two different `--now-file` values (an earlier one, then a later one). The second run pruned more than the first. Is that a violation of idempotency?**

No — idempotency (Section 10.6) guarantees that re-running with the *same* reference time produces no redundant work and no double-counting; it does not, and was never meant to, guarantee identical output across *different* reference times. As `now` advances, more batches naturally age into eligibility, and a later run finding and pruning batches an earlier run correctly left alone (because they weren't expired yet at the earlier reference time) is expected, correct behavior, not a bug in either run.

**Q: Why HMAC-SHA256 for checkpoint signatures instead of an asymmetric scheme like Ed25519 or RSA?**

Mainly for consistency with the Key Management service's existing architecture, which was already built around symmetric secret distribution for other internal systems by the time ChainAudit needed a signing mechanism (Section 8, and the 2024-04-02 changelog entry). The real tradeoff worth understanding: an asymmetric scheme would let anyone hold a public key locally, indefinitely, and verify a signature without any live dependency on a key service at all — signature checking would never be able to fail with `kms_unavailable`, because it wouldn't need to ask anyone anything at verification time. HMAC's symmetric nature means *verifying* a signature requires the same secret that *produced* it, which is exactly why `verify` has a live, per-run dependency on reaching the Key Management service (Section 8), and exactly why the entire `legacy_unverifiable` / `revoked_key` / `kms_unavailable` machinery in this document needs to exist at all. An asymmetric scheme would trade that dependency away in exchange for a different set of operational concerns (public key distribution and rotation, which have their own failure modes) — this system made the choice it made based on what infrastructure already existed to build on, not because HMAC is categorically the right choice for every system with a similar shape.

**Q: Can a checkpoint's signature be verified offline, without reaching the Key Management service at all?**

No, not with the current HMAC-based scheme (see the previous entry) — the key material needed to recompute and compare the signature only exists behind the KMS's access-controlled API, by design, and is never persisted locally by ChainAudit (Section 8.2, and the 2025-01-27 changelog entry documenting why a local key-material cache was considered and rejected). Content checks (Section 4.4) and structural checks (Section 5) require no network access and can run fully offline; only the signature-check portion of `verify` needs KMS reachability.

**Q: Does `verify` let me check just one specific stream instead of the whole database?**

Not via a dedicated flag — `verify` always processes every row in `streams` in a single run (Section 12.1). If you only care about one stream's result, the practical approach is to filter the resulting JSON afterward (`jq '.streams[] | select(.stream_id == "...")' report.json`, or equivalent) rather than expecting the tool itself to skip other streams. Given that `verify`'s own cost is dominated by per-stream database I/O and hashing rather than by any fixed per-run overhead, running it against the whole database and filtering afterward is rarely meaningfully more expensive than a hypothetical single-stream mode would be.

**Q: Is there a limit on how many streams, events, or checkpoints a single ChainAudit database can hold?**

Nothing in this document imposes a protocol-level limit — the encoding format's own limits (Section 4.11) are generous (up to 65,535 bytes for identifiers, up to roughly 4 GiB for a single payload) and unrelated to how many rows a database can hold in total. In practice, the real ceiling is whatever SQLite and the underlying filesystem can comfortably handle as a single file, and how long a full `verify` run over that many rows takes to complete, neither of which this document sets a specific number for — those are capacity-planning questions for whoever operates a given database, informed by their own hardware and their own tolerance for how long a `verify` run should take, not a constant fixed by the wire format.

**Q: If someone changes a stream's `legal_hold` flag while `verify` is in the middle of a run against that same database, which value does the report reflect?**

Whatever SQLite's own read consistency guarantees provide for a single connection reading over the course of one query — in practice, for the kind of straightforward sequential table scan `verify` performs, this means the report reflects a consistent-enough snapshot that this scenario is not a documented concern, but ChainAudit does not go out of its way to hold a long-lived exclusive lock for the sole purpose of guaranteeing point-in-time consistency across an entire multi-stream run either. Operational practice (Section 2.4) already recommends running `verify` during ingest-quiet windows or against a snapshot specifically to avoid needing to reason about this kind of mid-run mutation at all.

**Q: Can I rely on the order of the `streams` array in the JSON output?**

Yes — both `verify_report.json` and `compact_manifest.json` list streams sorted by `stream_id` ascending (Section 6.6, Section 12.1, Section 12.2), deterministically, on every run against a given set of streams. This is a documented, intentional property, not an incidental one, precisely so tooling built on top of these reports (diffing two runs, for instance) can rely on stable positional comparison without needing to re-sort first.

**Q: What does "living document" in the header actually commit this document to, practically?**

That the document is expected to be wrong or incomplete in places at any given time — not because anyone is being careless, but because a system this precise inevitably surfaces edge cases faster than anyone can anticipate them in advance — and that finding a gap is expected to result in an amendment here, not a workaround that only lives in someone's memory or in a comment in the source code. A large fraction of the changelog entries in Section 16 exist specifically because someone found the document silent or ambiguous about something the running system needed a real answer to. If you find another one, the front matter's opening note is not a formality: file the amendment.

**Q: Does adding a brand-new stream to a database change any existing stream's `chain_tip_hash`?**

No. Each stream's `chain_tip_hash` is a self-contained fold over that stream's own checkpoints and nothing else (Section 6.2) — it has no dependency on any other stream's existence, configuration, or history. Adding a new stream does change `chain_tip_hash_overall` (Section 6.6), since that top-level value folds in every stream in the database, but every existing stream's own per-stream `chain_tip_hash` is completely unaffected, and will show up identically in the next report regardless of how many other streams come and go around it.

**Q: Two engineers ran `verify` against what they both insist is "the same database" and got different `chain_tip_hash_overall` values. What should they check first?**

That it's actually the same database file, at the same point in time — this is by far the most common explanation, not a determinism bug in the fold construction (Section 6.6, and the 2025-02-03 changelog entry, which addressed a genuine early ambiguity in the fold's ordering but was resolved well before this document's current revision). A file copied at a different moment, a snapshot taken before versus after an ingest batch landed, or one engineer pointing at a staging replica that lags production by a few minutes, will all legitimately produce different `chain_tip_hash_overall` values, because the underlying checkpoint chains genuinely differ. Confirm both engineers' `--db` paths resolve to files with matching sizes and modification times (or, better, matching content hashes of the database file itself) before suspecting the tool.

**Q: Do I need to run `verify` before every `compact` run, or are they independent?**

They're independent in the sense that `compact` does not require a `verify` report to exist or to have passed before it will run — nothing in `compact`'s own logic reads or depends on `verify`'s output (Section 2.6). But running `verify` immediately before (and again immediately after) a `compact` run is the standard operational pattern for a good reason: it's the only way to positively confirm, for this specific run, that the `chain_tip_hash` invariant held (Section 6.4, Section 12.5's chained example) and that nothing was already `corrupt` going into the pruning run in a way that might be worth investigating before permanently discarding the rows that back it up. Skipping the "before" `verify` doesn't make `compact` behave any differently, but it does mean you lose the ability to distinguish "this batch was already fine when we pruned it" from "we have no idea what state this batch was in when we pruned it," which matters more the more the pruned data matters.

**Q: A stream shows `checkpoint_count: 0` in every `verify` report we've ever run against it, going back months, even though `event_count` keeps growing. Is checkpointing broken for this stream specifically?**

Possibly, but not necessarily — this is exactly the ambiguity flagged in Section 6.5 and the corresponding 2025-03-17 changelog entry, and it's worth ruling out the mundane explanation before escalating. Check that stream's `checkpoint_interval`: if it's configured large relative to how many events the stream actually receives (a stream provisioned for an expected high volume that never materialized, for instance), it can genuinely take months of real ingestion to accumulate a single full batch, and `checkpoint_count: 0` for that entire time is completely normal, not a stuck process. If the math doesn't add up — `event_count` comfortably exceeds `checkpoint_interval` and still no checkpoint exists — that's when it's worth escalating to whoever operates the ingest pipeline's checkpointing process, since that process (not `verify` or `compact`) is what's responsible for actually cutting checkpoints, and this document's two subcommands have no ability to diagnose why it hasn't from the database state alone.

**Q: Our team is about to provision a brand-new stream. What do we actually need to decide before creating the `streams` row?**

Three values that cannot be safely changed later, so it's worth getting them right at creation rather than treating them as easy to adjust: `checkpoint_interval` (Section 3.2.2 — pick based on this stream's expected ingestion rate, balancing "small enough that events don't sit unprunable in the tail for unreasonable stretches" against "large enough to avoid excessive per-batch overhead"), whether and when to set `migrated_at` (Section 11 — if this stream's events are ever likely to need `legal_hold` tamper-evidence, there's little reason not to launch it already migrated, i.e. `migrated_at` set at or before its very first event, so every event it ever ingests is v2 from day one rather than accumulating a mix), and `retention_days` (Section 10 — the actual compliance or contractual retention requirement this stream needs to satisfy, which should come from whoever owns that requirement, not be guessed at by whoever happens to be filling out the provisioning form). None of these three has a system-wide default to fall back on if you don't decide (Section 3.2's point about `checkpoint_interval` applies in spirit to all three) — provisioning tooling requires an explicit value for each.

**Q: What's the actual difference between a stream's `status` being `corrupt` because of `tampered_event` versus `tampered_merkle_root`, in terms of what an operator should physically go look at?**

`tampered_event` (Section 13.1, `first_bad_seq` set) points you at a specific row: `SELECT * FROM events WHERE stream_id = ? AND seq = ?` and inspect that row's fields against whatever independent record of its original content might exist (application logs, a source system, a backup). `tampered_merkle_root` (`first_bad_batch` set) points you at a specific checkpoint and the `seq` range it covers, but not at any single row within it — the mismatch tells you the batch's *current leaf hashes, collectively*, don't fold to the signed root, without narrowing down which individual leaf (or leaves) changed. If you need to know exactly which row within a structurally-broken batch is the actual culprit, that requires manually recomputing each row's `leaf_hash` from its current content (the same computation Section 4.4 describes) and comparing each one against what a trusted backup or independent log recorded it as — `verify` itself doesn't do this row-by-row narrowing for a structural finding, only for content findings, because a structural check is fundamentally a check on the batch as a whole, not on any single row in isolation.

**Q: Both `verify` and `compact` sort streams by `stream_id`. Is that a lexical/byte-wise sort, or something locale-aware?**

Byte-wise ascending on the UTF-8 encoding of `stream_id`, the same comparison Section 6.6 specifies for the `chain_tip_hash_overall` fold — not a locale-aware or human-friendly collation of any kind. For `stream_id` values using only ASCII characters (the overwhelming majority in practice, Section 3.2.1) this coincides with ordinary alphabetical order and the distinction is invisible; it only matters for identifiers containing non-ASCII characters, where a locale-aware sort could plausibly order two strings differently than a byte-wise comparison would. Consistency with the fold construction is the reason for this choice — the sort order used for iteration and the sort order used for hashing need to be the same order, or the two would silently disagree about something that's supposed to be a single, unambiguous ordering.

**Q: A stream's `verify` entry shows `event_count` larger than any single checkpoint's span would suggest, even though `checkpoint_count` is small. Is that expected?**

Yes, and it's exactly the uncheckpointed tail (Section 3.4, Section 10.7) showing up in the numbers. `event_count` reflects every currently-present row regardless of whether it's covered by a checkpoint; `checkpoint_count * checkpoint_interval` (if you wanted to compute it) only accounts for the checkpointed portion. The difference between the two is the tail's current size — content-checkable, but not yet structurally summarized by any checkpoint and not prunable regardless of age (Section 10.7) until enough further events arrive to complete the next full batch. A large, slow-growing tail on an otherwise healthy, regularly-checkpointing stream is not itself a problem; it only becomes worth examining if it seems to be growing without bound relative to the stream's `checkpoint_interval`, which would suggest the checkpointing process itself has stalled (see the earlier FAQ entry on `checkpoint_count: 0` for the same underlying diagnostic distinction, scaled down from "no checkpoints ever" to "checkpoints happening, just falling behind").

**Q: Does the order in which `compact` evaluates a stream's checkpoints (ascending `batch_index`) matter for correctness, or is it just a convention?**

It's a convention that happens to also be convenient, but the correctness of `compact`'s output does not depend on evaluating batches in any particular order within a single stream, because each batch's eligibility (Section 10.1) is evaluated entirely independently of every other batch's — pruning batch 3 has no bearing on whether batch 5 is eligible, and vice versa. Ascending order is used because it produces a more naturally readable `batches_pruned` / `batches_retained` pairing in the manifest (Section 13.2) and because it matches the order checkpoints were originally created in, not because evaluating them in a different order would produce a different, incorrect result. Contrast this with the tip-chain fold (Section 6.2), where order is not merely conventional but load-bearing — folding checkpoints out of order there produces a different, and wrong, `chain_tip_hash` entirely.

## 15. Error Codes and Diagnostics Appendix

This section catalogs the specific error conditions both subcommands can encounter, the stable diagnostic code each logs to stderr alongside a human-readable message, the resulting exit code (Section 12.3), and the recommended remediation. These codes are stable identifiers meant to be grep-able in logs and referenced in internal incident notes; the human-readable message text around them may be reworded over time, but the codes themselves are not renamed once shipped.

### 15.1 Invocation and flag errors

| Code | Condition | Exit code | Example stderr | Remediation |
|---|---|---|---|---|
| `flag_missing_required` | A required flag (`--db`, `--out`, and for `compact`, `--now-file`) was not supplied. | 2 | `chainaudit: missing required flag --db` | Supply the flag. |
| `flag_unrecognized` | An unknown flag was passed. | 2 | `chainaudit: unrecognized flag --outpath` | Check spelling against Section 12.1 / 12.2. |
| `subcommand_unrecognized` | The first argument isn't `verify` or `compact`. | 2 | `chainaudit: unknown subcommand "verfy"` | Check spelling. |

### 15.2 Database-access errors

| Code | Condition | Exit code | Example stderr | Remediation |
|---|---|---|---|---|
| `db_open_failed` | The path given to `--db` does not exist, or is not readable by the invoking user. | 1 | `chainaudit: cannot open database at /var/lib/chainaudit/prod.sqlite: no such file or directory` | Check the path and permissions. |
| `db_not_sqlite` | The file at `--db` exists but is not a valid SQLite database file (bad file header). | 1 | `chainaudit: /var/lib/chainaudit/prod.sqlite does not appear to be a SQLite database` | Confirm this is really the intended file — a common cause is pointing at a backup archive or a partially-transferred file. |
| `db_schema_missing` | The database opens, but one or more of `streams`, `events`, `checkpoints` does not exist. | 1 | `chainaudit: table "checkpoints" not found — is this a ChainAudit database?` | Confirm the path; ChainAudit does not create schema on demand (Section 2.1). |
| `db_locked` | SQLite reports `SQLITE_BUSY` — another process holds a conflicting lock. | 1 | `chainaudit: database is locked (SQLITE_BUSY); another process may be writing to it` | Wait for the other process (likely the ingest pipeline, or a concurrent ChainAudit invocation — Section 2.4) to finish, or coordinate an ingest-quiet window. `compact` does not retry a lock indefinitely. |
| `db_write_failed` (`compact` only) | A `DELETE` failed for a reason other than a lock — disk full, I/O error, corruption detected by SQLite itself. | 1 | `chainaudit: delete failed for example-stream-001 batch 0: disk I/O error` | Investigate host-level disk health before re-running; this is not a ChainAudit-level condition to retry past. |
| `out_path_unwritable` | The path given to `--out` cannot be created or written (missing parent directory, permissions, disk full). | 1 | `chainaudit: cannot write report to /var/log/chainaudit/verify.json: permission denied` | Check the parent directory exists and is writable; ChainAudit does not create directories. |

### 15.3 `--now-file` errors (`compact` only)

| Code | Condition | Exit code | Example stderr | Remediation |
|---|---|---|---|---|
| `now_file_missing` | The path given to `--now-file` does not exist or isn't readable. | 1 | `chainaudit: cannot read --now-file at /tmp/now.txt: no such file or directory` | Create the file (Section 12.2's example: `date +%s > /tmp/now.txt`). |
| `now_file_empty` | The file exists but contains no content. | 1 | `chainaudit: --now-file at /tmp/now.txt is empty` | Populate it with a decimal unix timestamp. |
| `now_file_not_integer` | The file's content doesn't parse as a decimal integer (extra text, scientific notation, a floating-point value, non-numeric content). | 1 | `chainaudit: --now-file content "2024-09-15" is not a valid unix timestamp` | Use a plain decimal integer, e.g. `1726358400`, not a formatted date string. |
| `now_file_negative` | The parsed integer is negative. | 1 | `chainaudit: --now-file value -100 is negative; expected a unix timestamp` | Supply a non-negative unix-seconds value. Pre-1970 reference times are not supported for `--now-file` even though `events.ts` itself has no such restriction (Section 4.11) — this is a `compact`-specific input validation choice, not a general limitation of the timestamp format elsewhere in the system. |

### 15.4 Key Management client errors (`verify` only)

| Code | Condition | Exit code (of the overall run) | Example stderr | Effect on report |
|---|---|---|---|---|
| `kms_connect_failed` | TCP connection to `--kms-addr` could not be established (wrong host/port, service down, network partition). | 0 (this is a per-checkpoint finding, not a fatal error for the whole run) | `chainaudit: kms: connect to http://127.0.0.1:8500 failed: connection refused (key kms-2024-06-a, retrying...)` | Contributes `kms_unavailable` for the affected stream(s), Section 8.5. |
| `kms_timeout` | A request to the Key Management service did not complete within the client's timeout. | 0 | `chainaudit: kms: request for key kms-2024-06-a timed out after 3 attempts` | Contributes `kms_unavailable`. |
| `kms_rate_limited` | A `429` was received; logged at each retry attempt, not treated as terminal on its own. | 0 | `chainaudit: kms: 429 for key kms-2024-06-a, backing off (attempt 2)` | No direct report effect unless retries are exhausted (then becomes `kms_unavailable`, Section 8.4). |
| `kms_key_revoked` | A `410` was received. | 0 | `chainaudit: kms: key kms-2024-06-a returned 410 (revoked)` | Contributes `revoked_key` and an entry in `revoked_key_ids`, Section 8.3. |
| `kms_bad_response` | A `200` was received but the body did not parse as the expected JSON shape, or `key_material_hex` was not valid 64-character hex. | 0 | `chainaudit: kms: malformed response body for key kms-2024-06-a` | Treated the same as a service error — contributes `kms_unavailable`, since the key material could not actually be obtained despite the `200` status. |
| `kms_unexpected_status` | Any status code other than `200`, `410`, `429` was received. | 0 | `chainaudit: kms: unexpected status 503 for key kms-2024-06-a` | Contributes `kms_unavailable`, Section 8.5. |
| `kms_retry_exhausted` | The configured bounded number of backoff-and-retry attempts (Section 8.4) was reached without a `200` or a definitive `410`. | 0 | `chainaudit: kms: giving up on key kms-2024-06-a after 6 attempts over 14.2s (last error: 429)` | Contributes `kms_unavailable`. Logged with the specific attempt count and elapsed time so a human reviewing the log can judge whether the backoff schedule itself needs tuning, without that judgment being baked into the tool's classification logic. |
| `kms_tls_error` | `--kms-addr` uses `https://` and the TLS handshake failed (expired certificate, hostname mismatch, untrusted root). | 0 | `chainaudit: kms: TLS handshake failed for http://127.0.0.1:8500: certificate has expired` | Contributes `kms_unavailable`. Worth checking independently of ChainAudit — a KMS-wide expired certificate affects every consumer, not just this run, and is worth escalating to the Key Management team directly rather than only re-running `verify`. |

None of the KMS client errors are fatal to the overall `verify` run — a KMS problem affecting one key affects the streams whose checkpoints reference that key, and `verify` continues processing every other stream normally, still producing a complete report and exiting `0` (Section 12.3's point that exit code reflects whether the tool completed, not whether everything it found was good news).

### 15.5 Diagnostic checklist: a `verify` report doesn't look the way you expected

When a report shows something surprising, work through these in order before escalating:

1. **Confirm you're looking at the report you think you are.** Check `db_path` at the top of the file against the database you intended to check, and check the report's file modification time or any timestamp you captured when you ran the command. A stale report from an earlier run is the single most common source of "this doesn't match what I'm seeing in the database right now."
2. **Separate `status` from `reason` from the two `first_bad_*` fields.** They carry different information (Section 8.7); don't infer detail that isn't there — `status = "corrupt"` alone doesn't tell you whether it's a content problem, a structural problem, or a signature problem without also reading `reason`, and `reason` alone doesn't tell you whether both a content problem *and* a structural problem exist simultaneously without checking both `first_bad_seq` and `first_bad_batch` directly.
3. **For `legacy_unverifiable`, check `revoked_key_ids` before assuming `kms_unavailable`.** An empty array with `reason = "kms_unavailable"` means a transient or service-level problem, worth re-running to clear; a populated array with `reason = "revoked_key"` means a specific, durable, known key rotation, worth confirming against the Key Management team's rotation log but not worth re-running `verify` to try to clear.
4. **For an unexpected `tampered_merkle_root`, check the erasure log for that batch's `seq` range before escalating as an incident.** Section 9.5 and the corresponding FAQ entry in Section 14 cover this — it is a known, expected, self-resolving consequence of lawful erasure against an already-checkpointed batch, and is common enough in practice to check first rather than last.
5. **For an unexpected `tampered_event`, check whether the affected `seq` corresponds to a row that was recently touched by anything other than ingestion or the erasure path.** A direct manual database edit (a one-off support script, a manual data-fix, a migration that touched more than it should have) bypassing both sanctioned write paths (Section 3.3.3) is a far more common real-world cause than an actual external attacker, though both produce an identical signal and both deserve equally serious follow-up — this system cannot distinguish "authorized person made an unauthorized-path edit by mistake" from "unauthorized person made an edit," and treats both as equally worth surfacing.
6. **If nothing above explains it, treat the finding as real and escalate.** The whole point of this system is that a finding which survives this checklist is not explainable by any of the known-benign causes, and should be treated with the seriousness the `corrupt` status implies.

### 15.6 Worked triage walkthrough

To make Section 15.5's checklist concrete, walk through an actual (illustrative) finding end to end. Suppose a nightly `verify` run against a production database produces this entry for one stream:

```json
{
  "stream_id": "example-stream-007",
  "status": "corrupt",
  "event_count": 12,
  "checkpoint_count": 3,
  "chain_tip_hash": "5e91...redacted-for-brevity...",
  "first_bad_seq": null,
  "first_bad_batch": 1,
  "reason": "tampered_merkle_root",
  "revoked_key_ids": []
}
```

**Step 1 (confirm the report).** `db_path` matches the production path, and the report's generation time (captured separately by whatever invoked `verify`, since the JSON itself doesn't carry a self-referential timestamp beyond what `compact_manifest.json` records for `now`) is recent — this is a live finding, not a stale report from a prior incident that's already been resolved.

**Step 2 (separate the fields).** `status` is `corrupt` — this is unambiguously the urgent bucket, not `legacy_unverifiable`. `reason` is `tampered_merkle_root`, not `tampered_event`, so per the precedence order (Section 8.7) this is either the only problem or at minimum the highest-precedence one found; `first_bad_seq` being `null` is consistent with that — no content-level mismatch was found anywhere in this stream, only a structural one. `first_bad_batch = 1` tells us exactly which checkpoint to look at.

**Step 3 (`revoked_key_ids` is empty).** Not a key-rotation story at all; this checkpoint's key resolved fine. Rules out the entire `legacy_unverifiable` branch of Section 8.3 as a contributing factor — whatever's wrong here, it isn't about the Key Management service.

**Step 4 (check the erasure log).** Batch `1`'s `start_seq`/`end_seq` are looked up from `checkpoints` directly (`SELECT start_seq, end_seq FROM checkpoints WHERE stream_id = 'example-stream-007' AND batch_index = 1`), giving, say, `seq 20`–`29`. Cross-referencing the compliance team's erasure log for `example-stream-007` in that `seq` range turns up a right-to-erasure request processed against `seq 24` four days ago — squarely inside this checkpoint's already-signed range. This matches Section 9.5's documented mechanism precisely: an already-checkpointed event was lawfully tombstoned, its `leaf_hash` was correspondingly updated, and the batch's Merkle root — computed and signed before the erasure — can no longer be reconciled against the now-different set of leaf hashes.

**Step 5 (resolve, don't escalate).** Because the erasure log entry is dated, references the correct `seq`, and comes from the compliance team's own sanctioned tooling (not an unexplained direct database edit), this finding is fully explained as expected fallout from lawful erasure, not evidence of tampering. The correct action is to note the explanation (for anyone else who looks at this same report later) and expect this specific `tampered_merkle_root` finding to persist, unresolved by any means other than the batch's eventual pruning, until `example-stream-007`'s batch `1` ages into retention eligibility and `compact` removes it — at which point Section 5.7's pruned-batch handling takes over and the structural check stops being attempted for that batch entirely. No incident ticket, no page, no rollback of anything; the system did exactly what it was designed to do, and the diagnostic legwork in Steps 1 through 4 is what turns a superficially alarming JSON field into a confirmed non-event.

Contrast this with the same JSON shape but an empty erasure-log cross-reference: no erasure request against any event in `seq 20`–`29`, ever, from any authorized source. That version of this walkthrough ends at Step 4 with escalation, not resolution — the identical `reason: "tampered_merkle_root"` finding, the identical missing explanation, and now a genuine incident, because the one explanation this system knows how to rule a structural mismatch benign for turned out not to apply.

### 15.7 Common false-positive patterns at a glance

A consolidated summary of every "this looks alarming but has a known, benign explanation" pattern discussed across this document, gathered here as a single scannable table rather than requiring a full re-read to recall which section covered which pattern:

| Symptom | Known benign cause | How to confirm | Where it's covered |
|---|---|---|---|
| `status: "legacy_unverifiable"`, `reason: "revoked_key"` | Routine, scheduled key rotation | Cross-reference `revoked_key_ids` against the Key Management team's rotation log | Section 8.3 |
| `status: "legacy_unverifiable"`, `reason: "kms_unavailable"` | Transient KMS outage or rate limiting | Re-run `verify`; check whether the condition clears | Section 8.5 |
| `status: "corrupt"`, `reason: "tampered_merkle_root"`, no content-check failure alongside it | A lawful right-to-erasure request against an already-checkpointed event | Cross-reference the affected `seq` range against the compliance erasure log | Section 9.5, Section 15.6 |
| `chain_tip_hash` unchanged despite `event_count` growing | Stream hasn't yet accumulated a full `checkpoint_interval`-sized batch | Compare `event_count` against `checkpoint_interval`; if `event_count` is still below it, this is expected | Section 6.5 |
| `event_count` dropped, `checkpoint_count` unchanged | Successful, expected pruning | Compare against the corresponding `compact_manifest.json` for the same run | Section 3.4, Section 13.2 |
| `db_locked` error from `compact` | A concurrent process (ingestion, or another ChainAudit invocation) holding a conflicting lock | Confirm nothing else is scheduled against the same database at the same time | Section 2.4, Section 15.2 |
| Two reports for "the same" database show different `chain_tip_hash_overall` | The two reports weren't actually taken against the same file at the same instant | Compare `--db` paths, file modification times, or content hashes of the database files directly | Section 6.6, Section 14 |

Every row in this table has a corresponding row that is *not* benign and looks identical at first glance — a genuinely revoked key looks the same as one revoked for a bad reason, a genuine attack on a batch's leaf hashes looks the same as an erasure-driven mismatch, a stuck checkpointing process looks the same as one that simply hasn't hit its interval yet. This table exists to speed up ruling the benign explanation in or out quickly, not to suggest any of these symptoms should be assumed benign without checking.

## 16. Changelog / Dated Amendment History

This document is a living document in the literal sense: it is amended in place as the system it describes evolves, as ambiguities in earlier revisions are discovered and resolved, and as incidents surface gaps between what was written down and what actually needs to be true. Amendments are proposed the same way code changes are — written up, reviewed by at least one of the other named authors or reviewers in the front matter, and merged with a dated entry below explaining what changed and, more importantly, *why*. Entries are never deleted or silently rewritten; if a later entry reverses an earlier one, both stay in the record, because the history of what was tried and rejected is itself useful information for the next person who has the same idea. What follows is the complete history, oldest first.

**2024-03-04 — Priya Ramaswamy.** Initial draft of this document (v0.1) published for review, covering the core data model, the canonical encoding, and a first pass at the Merkle construction. The motivating problem: the compliance team's existing audit-log tooling could tell you *that* a row existed, but had no mechanism for proving a row hadn't been altered after the fact short of comparing against an offline backup by hand, which nobody was actually doing in practice because it didn't scale past a handful of manual spot-checks a quarter. This RFC exists to replace "nobody's actually checking" with a structure where checking is cheap, mechanical, and doesn't require trusting the database file itself.

**2024-03-11 — Priya Ramaswamy.** Security review (Alex Feng) of the v0.1 prototype flagged that leaf hashes and internal node hashes were being computed with no distinguishing prefix — both were plain `SHA256(left || right)` for internal nodes and plain `SHA256(canonical_encoding(event))` for leaves, with nothing structurally preventing a 32-byte value produced by one construction from being replayed somewhere the other was expected. This is the classic leaf/node type-confusion class of bug that has bitten more than one naively-designed Merkle tree elsewhere in the industry. Fixed by introducing the four domain-separation prefix bytes (`LeafPrefix`, `NodePrefix`, `GenesisPrefix`, `TipPrefix`) described in Section 4.1, prepended to every hash construction in the system. Because this changed every hash in the system, it required a full backfill of the (at the time, small — this was pre-GA) set of staging streams. Nobody wants to do that backfill again against a production corpus, which is exactly why these four prefixes are treated as permanently fixed going forward rather than as a detail anyone should feel free to "clean up" later.

**2024-03-18 — Priya Ramaswamy, reviewed by Marcus Oyelaran.** Marcus's first substantive review on this project (he formally joins the DICE rotation the following month) caught that our Merkle-folding prototype had been copied from a reference implementation that used Bitcoin-style duplicate-last-node handling for odd leaf counts. Explicitly rejected in favor of the RFC 6962 "split at the largest power of two below n" construction, both because duplicate-last-node produces a different, non-standard root that diverges from RFC 6962 the moment any level of the recursion has an odd count (which is most batches in practice, since there's no reason to expect `checkpoint_interval` to be a power of two), and because the reference implementation we'd copied from also lacked the domain-separation fix from the entry above, compounding the two issues. Section 5.4 documents the rejected construction in full, specifically so nobody reaches for it out of habit when porting logic from a different system.

**2024-03-25 — Priya Ramaswamy.** Checkpoint signing contract finalized. An earlier internal draft (never deployed anywhere, caught in review) signed the bare `merkle_root` with no other context folded into the signed bytes. Alex flagged the same category of concern as the domain-separation review two weeks earlier: a signature over a bare 32-byte root carries no information tying it to a specific batch of a specific stream, so a signature valid for one checkpoint would, by construction, also be a valid signature for any other checkpoint that happened to produce the same root. Fixed by binding `stream_id`, `batch_index`, `start_seq`, and `end_seq` into `CheckpointSigningBytes` alongside `merkle_root`, exactly as specified in Section 7. Recorded here because this is the second time in three weeks a "just hash/sign the one value that matters" instinct needed to be walked back in review, which says something about how tempting that shortcut is and how consistently it's the wrong call for this kind of system.

**2024-04-02 — Marcus Oyelaran.** KMS API contract drafted jointly with Ingrid Voss and the Key Management team. Landed on the three-status-code contract in Section 8 (`200`/`410`/`429`) rather than a richer set of application-level error codes in the response body, specifically so `verify`'s classification logic could key entirely off the HTTP status and not need to parse and trust an arbitrary JSON error shape for anything that affects verification outcomes. The Key Management team pushed back initially, wanting a `403` for "caller not authorized for this key" as a distinct case from `410`; we agreed that's a real distinction for their service to make operationally, but from ChainAudit's perspective both are "can't get the key material to check this signature," and folding them into different reason codes here would create a distinction `verify`'s output can't actually act on differently. `403` bundles into the "any other status" / `kms_unavailable` bucket as a result.

**2024-04-08 — Priya Ramaswamy.** Prototyped and then removed a `--repair` flag for `verify` that would have rewritten a mismatched `leaf_hash` to match a freshly recomputed value whenever a content check failed, framed at the time as a convenience for clearing up "probably just a bit-rot" mismatches without a full re-ingest. Removed before this ever shipped, after Alex pointed out the obvious and serious problem in review: a tool that can silently make tampered data "correct itself" is not a tamper-evidence tool at all — it's a tool an attacker who successfully modifies a payload can simply run against their own tampering to erase the evidence of it. `verify` is and remains strictly read-only (Section 2.5); there is no repair mode, and there will not be one. This is listed explicitly in the design goals (Section 1.2, "detection over prevention") specifically so this idea doesn't get quietly re-proposed by someone who wasn't around for this discussion.

**2024-04-15 — Priya Ramaswamy.** GA launch of v1 encoding, checkpointing (owned by the ingest pipeline), and `verify` (v1 — `compact` does not exist yet at this point; pruning was still a manual, ungoverned process at this stage, which was in fact the main pain point motivating `compact`'s design over the following two months). Shipped with `checkpoint_interval` as a single global constant (`500`, chosen somewhat arbitrarily as "seems reasonable") rather than a per-stream value, flagged in the launch review as a known simplification to revisit once we had more than one real production stream to learn from. That revisit happens in the 2024-07-15 entry below, sooner than expected, for reasons that entry explains.

**2024-04-22 — Priya Ramaswamy.** Fielded a reasonable question during launch-readiness review: should ChainAudit encrypt `payload` at rest itself, on top of whatever the underlying storage already provides, given how sensitive some audit payloads are? Decided against building this into ChainAudit: payload confidentiality at rest is a storage-layer and access-control concern, already addressed (or not) independently of whether an audit log happens to be tamper-evident, and conflating the two would mean ChainAudit needs to become a key-management consumer for encryption keys *in addition to* signing keys, doubling the KMS surface area this tool depends on for no integrity benefit — tamper-evidence and confidentiality are different properties, achieved by different mechanisms, and this system is scoped to the former. Recorded here mainly so the scope boundary in what is now Section 1.1 reads as a deliberate decision rather than an oversight to anyone who comes looking for encryption-at-rest support and doesn't find it.

**2024-04-29 — Priya Ramaswamy.** First production incident. A compliance spot-check comparing the count of rows flagged `tombstone = 1` against what could be independently corroborated by inspecting encoded bytes found that erased events and events that had legitimately never carried a payload were structurally indistinguishable at the encoding level — both erasure (implemented at the time as simply clearing `payload` to zero-length) and a genuinely-always-empty payload produced the same `payload_marker = 0x00`, `payload_len = 0` shape. Nothing was cryptographically broken and no tampering had occurred, but the hashed record carried no independent, tamper-evident trace that erasure specifically had happened — the only signal was the `tombstone` column itself, which was not meaningfully bound into the payload-shape portion of the encoding at the time. Full incident writeup lives in the compliance team's own tracker; the fix is the subject of the next entry.

**2024-05-06 — Priya Ramaswamy, with Dana Whitfield (joining DICE as compliance engineering liaison this month).** Introduced `TombstoneSentinel` and the sentinel-substitution rule described in Section 4.7 and Section 9.3: a tombstoned event's canonical encoding now unconditionally uses the fixed 32-byte sentinel in place of the payload, with `payload_marker = 0x01` and `payload_len = 32`, making the erased-versus-never-had-one distinction structurally unmistakable rather than dependent on an unhashed-in-effect flag. Historical rows already tombstoned under the old (ambiguous but not cryptographically broken) scheme were backfilled by the compliance data-ops team: `leaf_hash` recomputed under the new sentinel-substituted encoding for every already-tombstoned row, in a one-time, carefully audited batch job outside ChainAudit's own scope. This is Dana's first changelog entry and the beginning of a much closer working relationship between DICE and compliance engineering that shapes a lot of what follows in this document.

**2024-05-13 — Marcus Oyelaran.** Pre-staging-rollout code review caught that `verify`'s database connection was still being opened in the driver's default read-write mode, a leftover from early development (including, probably, some of the now-removed `--repair` prototyping from 2024-04-08) that had simply never been tightened once `verify` settled into being genuinely read-only in practice. Nothing had actually gone wrong — `verify`'s code path never issues a write statement — but "never issues a write in the current code" and "cannot issue a write even if a future change accidentally adds one" are different guarantees, and only the second is one this document should be able to make in Section 2.5. Fixed by opening the connection with an explicit read-only DSN mode, so that any future accidental write attempt fails loudly at the driver level rather than silently succeeding.

**2024-05-20 — Dana Whitfield, with Priya Ramaswamy.** Design of the `compact` subcommand begins. First draft of the retention and legal-hold eligibility rules (Section 10.1) — age-based expiry plus a hold mechanism, both stream-level and event-level from the start, since compliance's existing (manual, pre-ChainAudit) pruning process already had informal versions of both and we didn't want to ship something with less expressiveness than what people were already improvising.

**2024-06-03 — Priya Ramaswamy.** Extended debate (see the design doc thread, linked from the internal ticket for this entry) over whether pruning should support partial-batch deletion — remove only the individually-expired, individually-unheld rows within a batch, leaving the rest — versus whole-batch-only. Partial deletion was more appealing operationally at first glance (it prunes more, sooner) but was rejected once we worked through what it would do to structural re-verification: a partially-deleted batch has no coherent way to have its Merkle root re-derived or confirmed, since the checkpoint's signed root covers the batch as a whole unit and there's no way to recompute "the root over some unspecified subset of the original leaves." Finalized as whole-batch-only (Section 10.4), with the 49-of-50 scenario (a single held event blocking 49 long-expired ones) as the standing example for why this is correct rather than merely conservative.

**2024-06-17 — Priya Ramaswamy.** GA launch of `compact`. First production pruning run, against the three lowest-risk staging-adjacent streams, went cleanly; wider rollout followed over the subsequent two weeks once we'd confirmed `chain_tip_hash` really did hold steady across real pruning runs, not just in the worked arithmetic in the design doc.

**2024-06-24 — Marcus Oyelaran.** Hardened `cmd/mockkms` (Section 2.3) from the bare-bones fixed-response stub it had been since roughly the KMS contract landing in April into a proper reference implementation supporting per-key-id configured response sequences — a key entry can now be configured to return `429` for a specified number of requests before flipping to `200`, or to return `410` unconditionally, or to return `200` with specific key material, all driven by a small configuration file rather than hardcoded branches in the mock server itself. Motivated by wanting to actually exercise `verify`'s retry-and-backoff behavior (Section 8.4) end to end during development, which was previously only possible by trying to catch the real Key Management service in a bad moment, an unreliable and unrepeatable way to test anything.

**2024-07-02 — Marcus Oyelaran.** Resolves the open question recorded inline in Section 8.3.1 (raised 2024-06-25, during KMS contract hardening work following the April API design): should `status` carry a fourth value to separate "key rotated, permanently and expectedly unverifiable" from "KMS unreachable right now, possibly transient"? Decision: no. `status` stays at exactly three values (`ok`, `legacy_unverifiable`, `corrupt`); the distinction lives in `reason` (`revoked_key` versus `kms_unavailable`), both mapping to the same coarse `legacy_unverifiable` status. Rationale: `status` is meant to answer "does a human need to react with urgency," and neither a routine key rotation nor a transient KMS blip clears that bar on its own — collapsing them at the `status` level keeps that signal clean, while `reason` preserves the finer distinction for anyone who needs it (which, per the FAQ entries in Section 14, is a real and common need — just not one that should compete for attention with the urgent `corrupt` signal).

**2024-07-15 — Priya Ramaswamy.** `checkpoint_interval` migrated from the single global constant (`500`, since GA — see 2024-04-15) to a required, explicit per-stream column, exactly as specified in Section 3.2. This was forced by onboarding a large customer whose compliance-critical, low-volume audit stream needed a much smaller interval (so it wouldn't sit in the uncheckpointed tail, unprunable regardless of age, for months at typical ingestion rates — Section 10.7) while their much higher-volume operational streams needed a considerably larger interval than `500` to avoid excessive checkpoint overhead relative to event volume. A single global constant could not serve both well simultaneously, and "pick a compromise value" would have meant the low-volume stream stayed effectively unprunable and the high-volume streams over-checkpointed relative to what they needed. This is why the current spec is so emphatic that there is "no global constant to fall back on" — an earlier version of this system had exactly such a constant, and removing it required a schema migration and a one-time backfill of the (by then, several dozen) existing streams' `checkpoint_interval` values from the old global default. Nobody wants to do that migration again either; per-stream configuration is the permanent design from here forward.

**2024-07-29 — Dana Whitfield, with Priya Ramaswamy.** Legal Engineering (Rahul Deshmukh) flags, during a review of ChainAudit's coverage for an upcoming litigation-hold process, that the v1 encoding does not hash `legal_hold` — meaning an event's legal-hold flag could in principle be silently cleared by anyone with direct database write access, without that change being detectable by any check `verify` performs. This is treated as a priority-one gap once understood, since it undermines the retention protections in Section 10 independent of anything else going right or wrong in the system, and design work begins immediately on what becomes the v2 encoding.

**2024-08-05 — Priya Ramaswamy.** While designing v2, considered and rejected packing an explicit `tombstone` bit into the new trailing v2 byte alongside `legal_hold` (a two-bit byte instead of a one-bit one), on the reasoning that if we were already adding a trailing byte for one piece of previously-unhashed metadata, we might as well make `tombstone` itself doubly explicit in the same place. Rejected once we worked through it: `tombstone` status is already fully and unambiguously reflected in the hashed bytes via the `payload_marker`/`payload_len`/`payload_bytes` shape (Section 4.7) — a tombstoned event's encoding is already structurally impossible to produce except by way of the sentinel substitution. Adding a second, redundant, explicitly-hashed tombstone signal wouldn't add any tamper-evidence that isn't already there, and would introduce a new failure mode of its own: a future bug that sets one signal without the other (the explicit bit flipped without the payload shape changing, or vice versa) would create an internally-inconsistent encoding with no defined meaning, purely because we'd built in two independent ways of saying the same thing. One canonical signal per fact, encoded exactly once, stays the rule.

**2024-08-12 — Priya Ramaswamy.** v2 encoding finalized: `legal_hold` added as a trailing byte, present only for v2-encoded events, with encoding version determined per event (not per stream) by comparing the event's own `ts` against a new `streams.migrated_at` column (Section 4.2, Section 11.1). The per-event, timestamp-driven approach was chosen over the alternative we considered and rejected — a single "encoding version" column on `streams`, flipped atomically for the whole stream — specifically because a stream-level flip would require an atomic, all-at-once re-encoding (and re-hashing, and re-checkpointing) of every already-ingested event to keep it consistent with the new version, which is exactly the kind of expensive, risky, one-shot migration this design avoids everywhere else. The per-event rule means migration is just setting one timestamp column and is complete the instant it's set, with old events staying exactly as they were, forever.

**2024-08-26 — Priya Ramaswamy.** Documented the v1→v2 migration's interaction with checkpoint batches that straddle the migration boundary (Section 4.2, Section 5.6) — worked through in detail after a reasonable question came up in review: does the Merkle construction need to know about mixed-version batches at all? Answer, confirmed by working the arithmetic by hand before writing it down here: no. Leaf hashes are leaf hashes regardless of which encoding version produced them, and folding them into a Merkle root never inspects or needs to inspect version. This section exists mostly to make that confidence explicit and demonstrated rather than asserted, since "are you sure that's fine?" came up more than once in review before the worked example settled it.

**2024-09-09 — Marcus Oyelaran.** First stream in production actually migrates to v2 and accumulates its first mixed-version checkpoint batch, exercising the straddling case from the 2024-08-26 entry against real data for the first time rather than only worked examples. Went exactly as documented — flagged here mainly as a confidence-building milestone and because it prompted a small doc clarification (folded into what is now Section 5.6) making even more explicit, with the real batch's structure as an example, that Merkle construction genuinely does not branch on version anywhere in the implementation.

**2024-09-23 — Dana Whitfield.** Legal placed a litigation hold spanning an entire stream — thousands of events, effectively all of a mid-sized tenant's audit history — and the existing per-event `legal_hold` flag proved operationally painful to apply at that scale: tagging every individual row correctly, and confirming none were missed, was slow and, worse, error-prone in exactly the way a hold can least afford to be (a single missed row is a single row that could be lawfully pruned out from under an active hold). Added `streams.legal_hold` as a coarser, whole-stream mechanism (Section 10.2) specifically for this situation — a single flag that cannot be partially or incorrectly scoped the way thousands of individual row-tags could be. Per-event `legal_hold` remains for the more common, narrower case of holding specific events without affecting the rest of their stream.

**2024-09-30 — Marcus Oyelaran.** Two separately-scheduled cron jobs — one intended to run `verify` nightly, one running an ad hoc `compact` a different team had set up without looping DICE in — collided against the same production database, and `compact` surfaced a `db_locked` error mid-run (Section 15.2) that paged on-call for a condition that turned out to be entirely benign once diagnosed, just poorly signposted. Nothing was corrupted — SQLite's own locking did exactly what it should have — but the incident made clear that the concurrency assumptions in what is now Section 2.4 had never actually been written down anywhere a second team could have found them before scheduling their own job against a database DICE also operates against. Documented explicitly, and added `db_locked` as a named, expected diagnostic code (Section 15.2) rather than letting it surface as an unlabeled SQLite driver error, specifically so the next person who hits this can recognize it immediately from the log line rather than needing to page someone who already knows the system.

**2024-10-07 — Dana Whitfield.** Added the worked 49-of-50 retention example (Section 10.4) after fielding the same support question — "if most of a batch is expired but one event isn't, does the batch get partially pruned?" — from three different people in the same month, which suggested the design doc's prose explanation of whole-batch-only pruning (2024-06-03 entry) wasn't landing on its own without a concrete worked number attached to it.

**2024-10-21 — Priya Ramaswamy.** Two additions prompted by the same review cycle. First, explicitly specified `compact`'s idempotency guarantee (Section 10.6) — that re-running against an unchanged database and `--now-file` must not re-count or re-process already-pruned batches — after an operator reasonably asked whether it was safe to put `compact` on a recurring schedule without separately tracking what a previous run had already done. Second, added the note in Section 3.1 about unix-seconds timestamp columns and the timezone-round-trip footgun, after watching someone eyeball a raw `ts` integer in a debugger, mentally convert it assuming local time, and reach an incorrect conclusion about whether an event was inside or outside its retention window — the arithmetic in this system is arithmetic on integers, not on any particular calendar representation, and losing sight of that is an easy mistake to make under time pressure.

**2024-11-04 — Marcus Oyelaran.** KMS incident. A different internal tool (not ChainAudit) that also consumes the Key Management service's read API implemented a retry loop with a fixed, short retry interval and no jitter; during a brief KMS deploy-related blip, every instance of that tool began retrying in near-lockstep, and the resulting request volume degraded the Key Management service broadly enough that `verify` runs elsewhere — including ours — started seeing elevated `429` rates as collateral damage for the better part of an afternoon. Nothing in ChainAudit's own client caused this, but it motivated formalizing the backoff-and-jitter retry guidance in Section 8.4 explicitly in this document (it had previously been "obviously you should back off," unstated and unenforced anywhere), and sharing it with the Key Management team as a recommended pattern to point other internal consumers at, specifically so this doesn't happen again from a different tool six months from now.

**2024-11-18 — Priya Ramaswamy.** Resolves the open question recorded inline near Section 8.5 (raised by Dana, 2024-11-05, while writing the diagnostic-checklist material that became Section 15.5): should `first_bad_batch` be populated for a checkpoint whose signature check couldn't be attempted at all (`410` or a KMS service error), so there's a specific batch coordinate to point at instead of just a stream-level `reason`? Decision: no — `first_bad_batch` is reserved for checks that were actually performed and concretely failed (a structural mismatch, or a signature mismatch against a key that *did* resolve successfully). A `410` or a service error means the check couldn't be attempted, which is a meaningfully different situation from attempting it and getting a negative result, and conflating the two would blur exactly the distinction Section 8.3 spends the most space on. `revoked_key_ids` remains the correct, and sufficient, breadcrumb for the revoked-key case.

**2024-12-02 — Priya Ramaswamy.** Added the explicit reason-code precedence table (Section 8.7) after realizing the spec had never actually stated what happens when a single stream has more than one distinct finding at once — a real and not even particularly rare situation, as it turns out, once we went looking at production data for streams with both an old revoked-key checkpoint and an unrelated, more recent content issue. Precedence order (content failures rank above structural, which rank above signature, which rank above revoked-key, which ranks above KMS-unavailable) was chosen to keep the single `reason` field always pointing at the most actionable, most concerning finding when more than one is present, while explicitly documenting that `first_bad_seq` and `first_bad_batch` remain independently populated regardless of precedence, so nothing is actually hidden — only the single-value `reason` field has to pick a headline.

**2024-12-16 — Marcus Oyelaran.** Second KMS-related incident, different in kind from November's: a key rotation was performed by the Key Management team without the advance notice that had, up to this point, been an informal courtesy rather than a tracked process. Several streams' most recent checkpoints started returning `410` with no warning, and — because `verify_report.json` at the time reported `status: "legacy_unverifiable"` with no indication of *which* key was responsible — the on-call engineer who got paged (unnecessarily, as it turned out; this was routine rotation, just unannounced) spent over an hour manually correlating checkpoint `key_id` values against the Key Management team's internal rotation log before confirming nothing was actually wrong. Added `revoked_key_ids` to `verify_report.json` (Section 13.1) directly as a result, so this correlation is immediate from the report itself next time, and pushed (successfully) for the Key Management team to formalize rotation notifications to downstream consumers rather than relying on this incident's fix alone to prevent a repeat.

**2025-01-06 — Priya Ramaswamy.** An internal client library computing `stream_id_len` using a rune-count function instead of a byte-length function was caught in code review (not in production, fortunately) while onboarding a new stream whose identifier included non-ASCII characters. Would have produced an incorrect length prefix, and therefore incorrect encoding, and therefore a `leaf_hash` at ingestion time that wouldn't match what any spec-compliant implementation would compute — a self-inflicted, permanent content-check failure baked in at the moment of ingestion. Section 3.2.1 and Section 4.11 were tightened to state the UTF-8-byte-length requirement as explicitly and repeatedly as reasonable, since this is exactly the kind of mistake that's invisible in testing against ASCII-only stream identifiers (the overwhelming majority of them, which is exactly why it slipped through initial review of that client).

**2025-01-20 — Marcus Oyelaran.** While building better structural-anomaly detection for an internal dashboard, realized the spec had never actually stated what `verify` should do if a checkpointed batch is found with some, but not all, of its rows present — a state that a correctly-operating `compact` should never produce (Section 3.5.5, Section 10.4), but which the spec hadn't explicitly said `verify` should still detect and react to if it somehow occurred. Documented explicitly: treated as a structural anomaly, reported as `tampered_merkle_root` with `first_bad_batch` set, on the reasoning that a batch's row population not matching what its checkpoint attests to (fully present or fully absent, nothing between) cannot correspond to any legitimate `compact` operation and is worth surfacing loudly rather than silently ignoring or, worse, silently attempting a partial recomputation that would be meaningless.

**2025-01-27 — Marcus Oyelaran.** Proposed, prototyped, and then rejected a local on-disk cache of resolved `key_material` keyed by `key_id`, intended to reduce KMS load and speed up repeated `verify` runs against large databases with many checkpoints sharing a small number of keys. Reverted before merging: caching key material to disk, even briefly, even locally, means a second place key material can potentially leak from — a compromised host running cached-and-stale key material would present a bigger attack surface than a host that only ever holds key material transiently in process memory for the duration of a single lookup-and-verify operation, and the actual performance win was marginal anyway once we measured it, since `verify` already deduplicates KMS lookups per distinct `key_id` within a single run (Section 8.1) and most of a run's wall-clock time is spent on database I/O and hashing, not on KMS round-trips. Filed here so the idea doesn't get re-proposed on performance grounds without someone first checking whether the performance problem it would solve is actually the bottleneck.

**2025-02-03 — Priya Ramaswamy.** `chain_tip_hash_overall`'s fold construction (Section 6.6) written up explicitly, with a full worked example, after two engineers independently implemented client-side verification of a `verify_report.json` against hand-recomputed stream tip hashes and got different answers for `chain_tip_hash_overall` — traced to one of them folding streams in the order they appeared in the JSON array (which happened, in that particular report, to already be `stream_id`-sorted, masking the bug for months) and the other folding in an arbitrary map-iteration order in their client language of choice. The fold's dependence on `stream_id`-ascending order had been true since the field was introduced but had never been written down explicitly enough to be unambiguous to someone implementing a client against this doc alone rather than against the reference Go implementation.

**2025-02-17 — Dana Whitfield.** An internal pruning-progress dashboard had been summing `batches_pruned` across historical `compact_manifest.json` files under the assumption that the field was cumulative per stream, producing wildly inflated "total batches pruned" figures once a stream had been through several `compact` runs. Root cause was a documentation gap, not a code bug: `batches_pruned` was always correctly scoped to "pruned by this specific run" (Section 10.6), but the spec's wording at the time didn't make that scoping unmissable. Tightened the field description in Section 13.2 and added the explicit idempotent-re-run JSON example showing an empty `batches_pruned` array on a second run, specifically so this can be checked against the spec text directly rather than inferred.

**2025-03-03 — Priya Ramaswamy.** Documented explicitly, in one place (Section 3.2.2 for `checkpoint_interval`, Section 11.3 for `migrated_at`), that both columns are immutable after being set, and specifically why: both are inputs to hash derivations that get permanently frozen into already-computed `leaf_hash` and checkpoint values at the time they're used, and changing either later desynchronizes future recomputation from what was actually stored, producing systemic false-positive corruption findings rather than any actual data problem. This had been true and (mostly) understood informally since the 2024-07-15 and 2024-08-12 entries respectively, but had never been stated as a named, general rule with the underlying mechanism spelled out — it took a near-miss during an internal tooling change (caught in review before reaching production) that would have "fixed" a misconfigured `migrated_at` in place to prompt writing this down properly.

**2025-03-10 — Dana Whitfield.** A reasonable question came up while a new engineer was reading through Section 7: since `CheckpointSigningBytes` binds in `batch_index`, `start_seq`, `end_seq`, and `merkle_root`, why not `created_at` too, for extra binding? Answered, and folded into Section 6.2 and Section 7.1's existing text rather than added as new material: `created_at` is bookkeeping about *when* a checkpoint was cut, not part of *what* it attests to, and binding it into either the signature or the tip fold would mean two checkpoints that are otherwise identical in every cryptographically meaningful way (same batch, same root, same key) would need to be treated as distinct if they merely happened to record different creation timestamps — which isn't a distinction anything in this system needs to make, since `created_at` is never compared against anything or used as an input to any eligibility or verification decision. Recorded here because it's a good instance of the general principle worth naming explicitly: not everything about a checkpoint needs to be cryptographically bound just because it's sitting in the same row: only the fields whose integrity actually matters to some check downstream belong in a signed or folded construction.

**2025-03-17 — Marcus Oyelaran.** Documented the "stream with events but zero checkpoints still reports `chain_tip_hash = Genesis(stream_id)`" edge case explicitly (Section 6.5), after fielding a question from a new SRE on the rotation who — reasonably, on first exposure to the system — assumed a stream showing thousands of `event_count` but a `chain_tip_hash` unchanged since stream creation must indicate a stuck or broken checkpointing process. In this particular case checkpointing genuinely wasn't stuck; that specific stream's `checkpoint_interval` was just large relative to its ingestion rate, and it hadn't yet accumulated a full batch. Worth a dedicated edge-case writeup specifically because the symptom (a "frozen-looking" `chain_tip_hash`) looks so similar whether the underlying cause is "totally normal, just hasn't hit the batch boundary yet" or "checkpointing is actually stuck" — this document can tell you the former is possible and expected, but distinguishing the two in a specific instance is still an operational judgment call, not something the JSON report resolves on its own.

**2025-03-31 — Dana Whitfield.** A new compliance analyst configuring a stream for data with effectively no retention requirement beyond "must be checkpointed at all" asked whether `retention_days = 0` was actually supported or would be rejected as a degenerate input. It's supported (Section 10.8) and always has been — nothing in `compact`'s eligibility logic special-cases zero — but this had never been stated as a deliberately-supported configuration anywhere in the spec, so there was no way to answer the question by reading the document rather than reading the source. Added explicitly.

**2025-04-14 — Priya Ramaswamy.** Documented the rationale for `--now-file` as a required flag with no wall-clock fallback (Section 10.9, Section 12.2), after an operator asked, reasonably, why `compact` doesn't just default to the system clock the way almost every other tool that needs "the current time" does. Answer: reproducibility. A `compact` run's output should be a pure function of the database state and an explicit reference time, re-derivable and auditable after the fact, rather than silently depending on exactly when someone happened to press enter — which becomes important specifically when reconstructing or explaining a past compaction decision during an audit, well after the fact, when "whatever the clock said at the time" is no longer a useful or checkable answer.

**2025-04-28 — Marcus Oyelaran.** Clarified in Section 4.11 that ChainAudit itself enforces no payload size limit beyond the `uint32` length-prefix ceiling (~4 GiB), after an internal team asked whether they needed to chunk an unusually large payload before ingestion. Practical limits, to the extent they're wanted, are an ingestion-side policy decision for whoever owns a given stream, not a wire-format constraint — the encoding itself has no opinion beyond what fits in the length prefix.

**2025-04-30 — Priya Ramaswamy.** A deployment automation script treated `chainaudit verify`'s exit code as a health check and started failing deploys whenever any stream in a routinely-checked staging database came back `corrupt` or `legacy_unverifiable` — which, since `verify` exits `0` whenever it completes successfully regardless of what it finds (Section 12.3), should never have happened, and turned out not to be `verify`'s exit code at all but a wrapper script's own added logic parsing the JSON and exiting non-zero on any non-`ok` status, undocumented anywhere outside that script. Not a ChainAudit bug, but it prompted stating the exit-code contract in Section 12.3 more forcefully than the original one-line mention had — "the tool ran successfully and told you the truth" and "the truth was bad" are different facts, and only the first belongs in an exit code, full stop — specifically so the next automation built on top of ChainAudit's output makes that separation deliberately rather than by accident.

**2025-05-06 — Dana Whitfield, with Priya Ramaswamy.** Fully documented the interaction between right-to-erasure and already-checkpointed batches (Section 9.5) after a real instance of exactly this scenario produced a `tampered_merkle_root` finding that briefly alarmed an on-call engineer who hadn't seen this interaction discussed anywhere. Cross-referencing against the compliance erasure log confirmed the finding was fully explained by a lawful, recently-processed erasure request against an event in an already-checkpointed batch — expected, once the mechanism is understood, but not previously written down anywhere despite being a direct, unavoidable mathematical consequence of two design decisions (immutable checkpoints, leaf-hash-recomputation-on-erasure) that had each individually been documented for almost a year. Added the worked explanation, the operational guidance to check the erasure log before escalating, and the corresponding entries in the FAQ (Section 14) and diagnostic checklist (Section 15.5).

**2025-05-09 — Dana Whitfield.** During the same onboarding round referenced in the next entry, noticed that the two new team members had each independently read the retention rules (Section 10), the Merkle construction (Section 5), and the JSON schemas (Section 13) as three unrelated topics, and had to be walked through, verbally, how a single checkpoint batch's story actually connects all three — checkpointed, aged, and eventually pruned, with the same `merkle_root` and the same `chain_tip_hash` value showing up in each section's worked examples without that continuity being called out anywhere. Added the full single-batch lifecycle walkthrough (Section 10.11) explicitly to make that connective tissue part of the document itself rather than something every new hire has to be told out loud once.

**2025-05-12 — Priya Ramaswamy and Dana Whitfield.** Substantially expanded the Operational FAQ (Section 14) while onboarding two new team members to DICE, using their actual first-week questions as the basis for new entries rather than trying to anticipate questions in the abstract — several of the entries added this round (the `stream_id` UTF-8 byte-length gotcha, the `first_bad_seq`-and-`first_bad_batch`-both-set clarification, the "can I undo a compact run" question) came directly from things a genuinely new reader of this document asked before finding the answer already present elsewhere in it, which is itself a useful signal about where the document's structure wasn't making existing content easy enough to find.

**2025-05-20 — Marcus Oyelaran.** Added the `status`/`reason` quick-reference matrix (Section 13.1) after watching a support engineer, unfamiliar with the precedence rules in Section 8.7, manually re-derive by trial and error which combinations of `status` and `reason` were even possible while triaging a batch of reports during a compliance audit walkthrough. The precedence prose in Section 8.7 was, and remains, the normative description of how these values are computed; the matrix is a derived, scannable summary of the same rules for exactly this kind of fast lookup, not a competing source of truth — if the two ever appear to disagree after some future amendment, Section 8.7 wins and the matrix has a stale-documentation bug that needs fixing to match it.

**2025-05-27 — Priya Ramaswamy.** Editorial reorganization of the full document into the numbered section structure with a table of contents used from this revision forward. No technical or behavioral content changed in this pass — every worked example, every field definition, every rule was checked against the previous revision during the reorganization and confirmed unchanged — but the document had grown organically over fourteen months of amendments to the point that finding anything required already knowing roughly where it lived, which defeats the purpose of a reference document. This is the current revision.


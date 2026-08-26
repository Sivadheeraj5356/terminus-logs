# vaultseal Key-Leak Triage Runbook

This runbook describes, at a working level, how a crash corpus from the
`vaultseal` crypto harness is triaged into a single deterministic
`triage_report.json` by the offline Terraform module in `/app/triage`. It tells
you the *shape* of the pipeline, the input formats, the output contract, and the
invariants the report must satisfy.

It deliberately does **not** spell out every exact rule — the precise severity
matrix, the exact clustering distance, the error-class precedence, the tie-breaks
for operation attribution and key selection, the exact gate comparison, and so
on. Those are defined by the **reference implementation**, shipped as an opaque
binary at `/app/oracle`. Treat the oracle as the source of truth: run it on any
corpus you construct and its `triage_report.json` is, by definition, correct.
Where a rule below is described only in general terms, determine the exact
behavior empirically from the oracle rather than guessing.

The concrete on-disk *encodings* — the fingerprint and decoy token formats, the
cluster id format, and the JSON layout — are established, correct module behavior
and must be preserved exactly, not re-derived.

## What the pipeline does

The module reads a *corpus directory* and writes one deterministic report
`triage_report.json` into an *output directory*. It:

1. parses each gdb backtrace and valgrind memcheck log,
2. matches gdb and valgrind logs that belong to the same case,
3. attributes each case to a cryptographic operation,
4. classifies the memory error,
5. detects and redacts key material, and flags real key leaks (including keys
   reused across cases),
6. groups near-identical crashes into clusters,
7. assigns each case a severity, orders the findings, and
8. trips a configurable severity gate that fails `terraform apply`.

Everything runs with no network access; the providers are already mirrored
locally, so `terraform init` works offline. The same corpus must always produce
byte-for-byte identical output.

## Corpus layout

A corpus directory contains two subdirectories:

- `gdb/` — one gdb backtrace snapshot per file
- `valgrind/` — one valgrind memcheck log per file

Files are plain text. Filenames are advisory; the authoritative case id lives
inside each file. A case may have a gdb file, a valgrind file, or both. Logs may
be malformed or truncated — a single bad file must never abort the run. A gdb
file and a valgrind file belong to the same case when their canonical ids match;
the canonical-id normalization is existing module behavior and should be
preserved as-is.

### gdb snapshot shape

```
vaultseal triage snapshot
case: case_0007
signal: SIGSEGV (fault)
#0  0x5555.... in rsa2048_sign (ctx=0x..., key=0x...) at vaultseal.c:201
#1  0x5555.... in seal_record (rec=0x...) at vaultseal.c:418
#2  0x5555.... in main () at vaultseal.c:520
key: 4c:db:41:...
```

The `signal:` token (first word after `signal:`) is the crash signal, or absent.
A stack frame is *only* a line of the exact form
`#N 0xADDR in FUNC (args) at FILE:LINE`; a line missing a valid `at FILE:LINE`
suffix is not a frame at all and contributes nothing. A `key:` line may carry raw
key bytes. Frame lists are normalized before use (in particular, an
immediately-repeated recursive frame is not counted many times); the exact
normalization is part of the behavior to match against the oracle.

### valgrind memcheck shape

```
==49781== Memcheck, a memory error detector
==49781== case: case_0007
==49781== Invalid read of size 8
==49781==    at 0x5555....: rsa2048_sign (vaultseal.c:201)
==49781==    by 0x5555....: seal_record (vaultseal.c:400)
==49781==  Address 0x5555.... is 8 bytes inside a block of size 32 free'd
```

## Cryptographic operations

Each case is attributed to a recognized cryptographic operation found on its
stack (gdb preferred, otherwise valgrind). Recognition is by *exact* function
name — a near-miss such as `aes256_gcm_sealer` is an ordinary frame, not a crypto
operation. When exactly one recognized operation is present on a side the choice
is unambiguous; when a stack names more than one, or when gdb and valgrind
disagree, the exact selection and the `operation_conflict` flag follow the
oracle. The recognized operations, their key sizes, and whether they carry secret
key material:

| operation          | key_bits | secret-bearing |
|--------------------|----------|----------------|
| aes256_gcm_seal    | 256      | yes            |
| aes256_gcm_open    | 256      | no             |
| rsa2048_sign       | 2048     | yes            |
| rsa2048_verify     | 2048     | no             |
| ec_p256_sign       | 256      | yes            |
| ec_p256_verify     | 256      | no             |
| hkdf_derive        | 256      | yes            |
| hmac_sha256        | 256      | no             |

With no recognized operation the `operation` and `key_bits` are `null` and the
case is treated as non-secret-bearing.

## Error class

Each case is assigned one memory error class, derived from its valgrind log (or
`unknown` when there is no valgrind log). The classes are `use-after-free`,
`invalid-free`, `invalid-read`, `invalid-write`, `uninitialized-value`, and
`unknown`. Several valgrind signals can be present at once; the precedence that
decides which class wins is defined by the oracle.

## Key material and redaction

A *key-length hex run* is a run of 16 or more consecutive two-hex-digit
byte-pairs, optionally `0x`-prefixed, with at most one separator (space, tab, or
colon) between pairs. Ordinary pointer addresses are shorter and are never keys.

Not every key-length blob is a real key: vaultseal keys carry a structural
integrity property, so only some runs are **real key material** and the rest are
**decoys**. The exact validity check is existing module behavior — match it to
the oracle. Only real keys drive leak state; a decoy never marks a case leaked.

Every key-length hex run is redacted out of any string emitted into the report so
no raw hex survives: a real key becomes a salted **fingerprint token** (`vsk1:`)
and a decoy becomes a **placeholder token** (`vsx1:`). The fingerprint depends on
the redaction salt; the decoy placeholder does not. These token encodings are
fixed module behavior and must be preserved exactly.

A case is **leaked** when at least one real key appears anywhere in its logs. Its
`leaked_key_fingerprint` is the token of one of its real keys (which one is
defined by the oracle), and `leak_context` is a redacted log line containing real
key material, or `null` when not leaked. A real key that surfaces in more than
one case is treated as reused across the corpus — a corpus-wide determination
that requires a pass over the whole corpus and that raises the `shared_key`
flag; the exact reuse threshold is the oracle's.

## Severity

Every case gets one of `low`, `medium`, `high`, `critical` (ordered
`low < medium < high < critical`). Severity is a function of whether the case
leaked a real key, whether that key is reused, whether the operation is
secret-bearing, and the error class. Leaked secret material is the most severe;
reuse of a leaked key escalates it further; memory errors and uninitialized
values contribute on their own. The exact decision matrix — including which
combinations land on which level and how a reused key escalates a non-secret
operation — is the oracle's; reproduce it exactly.

## Crash clustering

Crashes are grouped into clusters by *approximate* stack similarity, not exact
equality: near-identical crashes (one extra frame, one renamed frame) belong to
the same cluster. Define a case's **frame sequence** as the full, ordered list of
the function names of its gdb stack frames after the frame normalization above; a
case with no gdb frames has a fixed placeholder sequence. Clusters are the
**connected components** of the graph whose nodes are cases and whose edges join
sufficiently-similar frame sequences. Adjacency is not transitive, so this is a
genuine connected-components computation, and grouping by identical signature or
greedily assigning each case to the first cluster it resembles does **not**
reproduce it. The exact similarity threshold that defines an edge is the oracle's
— determine it empirically.

Each cluster carries a `cluster_id` (a stable opaque id, prefixed `clu:`, derived
from its member case ids — existing encoding, preserve it), a `signature` (the
representative case's frame sequence truncated to its first three names), a
`size`, a `severity` (the max over its members), and a `representative` (the
lexicographically smallest member case id). Every finding carries its cluster's
id. The `clusters` array is sorted by descending severity then ascending
cluster id.

## Report contract

Write `triage_report.json` to the output directory: a JSON object with two-space
indentation, object keys sorted, ASCII only, and a trailing newline — the same
corpus always yields byte-for-byte identical output.

Top level: `schema_version` (`"1.0"`), `generated_by` (`"vaultseal-triage"`),
`severity_gate`, `gated`, `max_severity` (or `null` with no findings),
`severity_counts` (per-severity histogram over `critical`/`high`/`medium`/`low`),
`corpus` (`{ gdb_cases, valgrind_cases, correlated, clusters, total_findings }`,
where `correlated` counts cases with both a gdb and valgrind file), `clusters`,
and `findings` (sorted by descending severity then ascending case id).

Each finding: `case_id`, `operation`, `operation_conflict`, `error_class`,
`crash_signal`, `key_bits`, `leaked`, `shared_key`, `leaked_key_fingerprint`,
`leak_context`, `severity`, `correlated`, `cluster_id`, and `gdb_frames` (the
leading gdb frames as `"FUNC at file:line"`, redacted; empty when no gdb file).

## Severity gating

The gate compares the report's `max_severity` against `severity_gate`. When the
report is gated, applying the module must fail (a non-zero exit from the analysis
surfaces as a failed `terraform apply`), and the report is always written first,
so the artifact exists even on a gated apply. Whether the comparison is inclusive
of the gate level is the oracle's behavior — match it.

## Performance and scale

A production corpus is large: a single nightly `vaultseal` fuzz run commonly
yields **tens of thousands** of gdb/valgrind cases, and the report has to be
produced quickly enough to be part of the run's teardown. Treat "must finish a
corpus of at least tens of thousands of cases in well under a minute on one core"
as a hard requirement. Everything except clustering is naturally linear. The
clustering step is the one place where the obvious implementation does not scale:
forming the adjacency graph by measuring similarity between **every pair** of
cases is O(n²) and will not finish in time. A conforming implementation computes
the same connected components without an all-pairs scan — indexing candidates and
confirming them — and its output must be byte-for-byte identical to the
components defined above; only the cost of getting there changes.

## Module interface

The Terraform module accepts `corpus_dir`, `output_dir` (defaults to
`<module>/out`), `severity_gate` (default `high`), and `redaction_salt` (default
`vaultseal`). Providers are mirrored locally; `terraform init` works with no
network access.

## Determining exact behavior

For anything this runbook leaves general, the reference oracle is authoritative:

```
/app/oracle --corpus-dir <dir> [--severity-gate high] [--redaction-salt vaultseal]
```

prints the canonical `triage_report.json` for that corpus to stdout. Build small
corpora that isolate a rule, run the oracle, and compare against what the module
produces. The oracle's source is not available; you are expected to learn its
behavior by running it, not by reading it.

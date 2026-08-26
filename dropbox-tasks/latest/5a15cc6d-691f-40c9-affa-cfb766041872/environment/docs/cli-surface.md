# CLI surface

Binary path after build: `/app/bin/siggate`.

## verify

```text
siggate verify --envelope <abs-path> --keyring <abs-path> --now <unix> --profile <abs-path> --seen <abs-path>
```

All of `--envelope`, `--keyring`, `--profile`, and `--seen` must be **absolute**
paths. A relative path for any of them is `usage` (before any file I/O or
crypto). All five flags are **required** (`--seen` is no longer optional).

Each flag accepts **both** forms: `--flag <value>` and `--flag=<value>`.
Duplicating a flag in either form (including two space-form repeats or mixing
space and equals forms) is `usage`. An empty equals value (`--envelope=`,
`--keyring=`, `--now=`, `--profile=`, `--seen=`) is also `usage`.

`--envelope`/`--keyring` must resolve to a regular file. A path that is a
directory is **not** `usage` — it is a non-blocking `envelope_invalid` /
`keyring_invalid` (the flag itself was well-formed; the referenced file is
not usable). Symlinks are followed transparently: a symlink whose target is
a valid regular envelope/keyring file works exactly like a direct path.

`--profile` must resolve to a regular file whose contents match `profile.md`.
A directory or unreadable path is `io`. A readable file with a bad layout is
`profile_invalid`.

`--now` must match `^[0-9]+$` (digit-only decimal) and must not use leading
zeros except for the value `0` itself. Values such as `+1700000100`, `-1`, or
`01700000100` are `usage`. Non-digit strings are `usage`. Flag order does not
matter.

### Success stdout

Exactly one line, then a single trailing newline:

```text
ok kid=<kid> digest=<content-digest>
```

where `<content-digest>` is the profile-framed token from `digest.md` /
`profile.md`.

Stdout must be byte-identical for identical successful inputs.

### Failure

Exit code `2`. Stderr contains exactly one line:

```text
error: <reason>
```

with a trailing newline. No other stdout on failure.

### Reason tokens

`usage`, `envelope_invalid`, `keyring_invalid`, `profile_invalid`, `io`,
`unknown_kid`, `missing_covered_header`, `invalid_window`, `not_yet_valid`,
`expired`, `bad_digest`, `bad_mac`, `replay`.

### Check order

First matching reason wins; stop:

1. CLI / path usage → `usage` (before any crypto)
2. Envelope / keyring / profile load problems → `envelope_invalid` /
   `keyring_invalid` / `profile_invalid` / `io`
3. Domain faults in the order encoded by `--profile` (see `profile.md`)

Examples under the sample profile order `1..6`: expired + bad MAC →
`expired`; wrong covered content-digest + bad MAC → `bad_digest`; bad MAC +
identity already in seen → `bad_mac` (not `replay`); unknown kid + invalid
window → `unknown_kid`. A profile that places code `5` before code `4` reports
`bad_mac` ahead of `bad_digest` when both are active.

### Keyring

JSON shape: `{ "keys": { "<kid>": "<standard-base64 key bytes>" } }`. Kid
lookup is exact and case-sensitive. Key material must decode as **standard**
base64 (alphabet `A–Z a–z 0–9 + /` with `=` padding as needed). URL-safe
base64 key material (alphabet using `-` or `_`) is `keyring_invalid`. The
keyring file itself must be strict UTF-8 JSON with no leading byte-order
mark; a BOM-prefixed or otherwise malformed keyring file is
`keyring_invalid` before any kid lookup happens.

### Replay (`--seen`)

`--seen` is required. After a successful MAC compare, the identity line is
exactly `kid|created|mac` (`created` decimal; `mac` as on the envelope).
Membership is **exact line equality** on non-empty lines (no trim, no
substring). CRLF-terminated seen lines leave a trailing CR after LF-split and
**must not** match; on success append a clean LF-terminated identity line.
Space/HTAB padding, prefix/suffix wrappers, and wrong `created` are not hits.
The ledger is durable across invocations that share the same `--seen` path. A
`--seen` path that resolves to a directory is `io` (append/open fails); do not
hang. A dangling space-form `--seen` with no following path token is `usage`.
Any bare positional argument after an otherwise-complete invoke is `usage`.

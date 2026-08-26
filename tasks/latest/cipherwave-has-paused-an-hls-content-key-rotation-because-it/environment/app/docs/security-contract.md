# Cipherwave security contract

This document defines the complete trust and decision behavior. Field types,
nullability, array order, and artifact bytes are fixed by
`artifact-contract.md`. Fallback trust sources, wall-clock time, network discovery,
and additional reason values are outside the contract.

## Profile policy

`profile.toml` has schema `cipherwave.profile.v2` and exactly these TOML keys:

| Key | Rule |
| --- | --- |
| `schema` | exact schema string |
| `profile_id` | nonempty ASCII token |
| `audit_unix` | explicit signed Unix second |
| `current_key_id` | exact key in the registry manifest's `keys` bucket export |
| `current_generation` | positive integer |
| `candidate_key_id` | different exact bucket key |
| `candidate_generation` | exactly `current_generation + 1` |
| `renditions` | sorted, unique, nonempty ASCII tokens |
| `allowed_key_hosts` | sorted, unique, lowercase ASCII DNS names |
| `trusted_spki_sha256` | sorted, unique, lowercase 64-hex SHA-256 values |
| `render_segment_count` | integer from 1 through 4 inclusive |

The supplied strict loader rejects missing/extra keys, duplicate TOML keys,
wrong types, unsorted/duplicate arrays, invalid tokens, and out-of-range values.
Security code receives a validated `contract.Profile`.

Source bindings use the semantic digests defined in `artifact-contract.md`, not
TOML whitespace or registry-manifest layout bytes.

## Trust roots and signed key records

`trust.json` has schema `cipherwave.trust.v1` and exactly:

```text
schema
issuers[]: issuerId, publicKey, notBeforeUnix, notAfterUnix, compromisedAtUnix|null
keyEncryptionKey
catalogSigner: signerId, publicKey
```

Public keys are 32-byte Ed25519 keys and `keyEncryptionKey` is a 32-byte
AES-256-GCM key; all use unpadded base64url. Issuer eras are half-open
`[notBeforeUnix, notAfterUnix)`. The same issuer ID may occur in
multiple eras only when the entries are sorted by issuer ID then
`notBeforeUnix` and those eras do not overlap. Qualification selects the unique
era containing `profile.audit_unix`; an absent ID is `unknown_issuer`, while a
known ID with no containing era is `issuer_out_of_era`. A selected era is
compromised for an audit when non-null
`compromisedAtUnix <= profile.audit_unix`.

The read-only registry manifest exports the logical `keys` bucket described in
`contract-map.md`. Its decoded values are strict JSON records with schema
`cipherwave.key-record.v1` and fields:

```text
schema, keyId, profileId, generation, issuerId,
notBeforeUnix, notAfterUnix, revokedAtUnix|null,
keyUri, spkiSha256, nonce, wrappedKey, signature
```

The bucket lookup key must equal `keyId`; a mismatch is `malformed`. `signature`
is a 64-byte unpadded-base64url Ed25519 signature over canonical JSON of the
record with only `signature` removed. There is no additional signature domain.
`nonce` is 12 bytes. `wrappedKey` is AES-256-GCM ciphertext followed by its tag.

GCM additional authenticated data is canonical JSON of exactly:

```json
{"generation":1,"keyId":"example","keyUri":"https://keys.example/key","profileId":"profile","schema":"cipherwave.key-aad.v1","spkiSha256":"0000000000000000000000000000000000000000000000000000000000000000"}
```

The values are the record values; the generation shown above is illustrative.
The unwrapped plaintext must be exactly 16 bytes.

An HTTPS key URI must be absolute, contain a host, contain no userinfo or
fragment, and have a lowercase-normalized hostname in `allowed_key_hosts`.
Only those listed constraints are imposed: a syntactically valid port, path,
or query is not independently rejected. Exact URI equality is used later when
matching playlists. `spkiSha256` must be lowercase 64-hex and occur in the
profile trust set.

## Key qualification

The current lookup precedes the candidate lookup. Each row uses
the profile's requested role, key ID, and generation even when the record is
missing or malformed. The first matching reason is authoritative in this order:

1. `missing`
2. `malformed`
3. `wrong_profile`
4. `wrong_generation`
5. `unknown_issuer`
6. `issuer_out_of_era`
7. `issuer_compromised`
8. `bad_signature`
9. `not_yet_valid`
10. `expired`
11. `revoked`
12. `invalid_uri`
13. `untrusted_spki`
14. `unwrap_failed`
15. `qualified`

`malformed` includes schema failure, an unequal record/bucket key ID, an
invalid/incorrect-length encoding, invalid integers, or a record that cannot be
strictly decoded. Key-record validity is half-open
`[notBeforeUnix, notAfterUnix)` at `audit_unix`; revocation applies when non-null
`revokedAtUnix <= audit_unix`.

For `qualified`, expose URI, SPKI digest, and this lowercase handle:

```text
HMAC-SHA256(
  key = unwrapped 16-byte content key,
  data = "Cipherwave key handle v1\0" || canonical_key_aad_bytes
)
```

For every other reason those three fields are null. `ready` is true only when
both rows qualify. The in-memory `KeyRing` may retain qualified key bytes for
the current process, but artifacts and errors never contain them.

## Signed fragment catalog

`catalog.json` has schema `cipherwave.catalog.v1` and exactly:

```text
schema, profileId, signerId, rows, signature
```

Each row has exactly:

```text
rendition, surface, playlistPath, segmentPath, keyId, generation, sequence,
ciphertextSha256, plaintextSha256
```

`surface` is `published` or `staged`. Paths are slash-separated relative paths
that must resolve below `media-dir`; absolute paths, `..`, or escape through a
symlink are invalid. Catalog rows are uniquely keyed by rendition, surface,
playlist path, segment path, and sequence, and sort by rendition, surface
(`published` before `staged`), then sequence and paths. The catalog must name
the requested profile and its exact configured catalog signer. `signature` is
Ed25519 over canonical JSON of exactly `{schema,profileId,signerId,rows}` with
no additional domain.

## Encrypted fragment evidence

First require the supplied custody file to be exact canonical LF-terminated JSON
for the current profile, audit, and source digests. Its exact bytes are hashed
into evidence. A stale, noncanonical, malformed, or source-mismatched custody
file is an integrity error (exit 3), not an evidence row.

Produce one `published` row and one `staged` row for every profile rendition,
ordered by rendition and then surface. First authenticate the catalog as one
authority. A bad signature, signer, schema, or profile, or any structurally
invalid, unsafe-path, duplicate, or out-of-order catalog row invalidates the
whole authority: emit the complete row universe as `present=false`,
`valid=false`, `catalog_invalid` with null metadata and empty fragments; none of
its rows is consumed.

After that whole-catalog check succeeds, a surface is present exactly when the
catalog contains at least one row for that rendition/surface; zero rows is
`absent`. A claimed surface whose otherwise safe path is missing, unreadable,
or escapes through a filesystem symlink is `present=true`, `catalog_invalid`
with its uniform key metadata retained and an empty fragment array. Conflicting
key IDs or generations within an authenticated claimed surface are
`mixed_generation`. Perform this surface-uniformity check before validating any
individual fragment; it therefore wins over fragment-level `unknown_key`, URI,
IV, or cryptographic failures.

For each cataloged fragment:

1. Select its effective `#EXT-X-KEY` and require `METHOD=AES-128`.
2. Require a qualified current/candidate key matching both key ID and generation.
3. Require the playlist URI to equal that qualified record's HTTPS URI exactly.
4. If `IV` is present, require `0x` followed by exactly 32 hexadecimal digits and
   use those 16 bytes. The prefix is case-sensitive: `0X` is invalid even when
   the following 32 digits are hexadecimal. Otherwise encode the fragment's
   rendition-local sequence as an unsigned 128-bit big-endian integer.
5. Hash readable ciphertext bytes and compare lowercase SHA-256 with the
   catalog; a mismatch is `cipher_digest_mismatch`.
6. Require nonempty ciphertext whose length is a multiple of 16.
7. AES-128-CBC decrypt with the qualified content key and IV.
8. Remove PKCS#7 strictly: the last byte is 1..16 and every one of that many
   trailing bytes equals it.
9. Hash recovered plaintext and compare it with the catalog. This final digest
   check is mandatory even when a wrong key happens to yield valid padding.

The parsed playlist and authenticated catalog are independent claims that must
also agree. The segment's effective URI is reported exactly as transmitted. If
it differs from the qualified catalog key's URI, the fragment is
`uri_mismatch`; do not relabel it `unknown_key` or infer a key from the URI. The
sequence computed as `#EXT-X-MEDIA-SEQUENCE` plus the segment's zero-based
playlist position must equal the signed catalog `sequence`; otherwise that
fragment is `playlist_malformed`. All parsed playlists contributing fragments
to one surface must report the same media sequence, or the surface is
`playlist_malformed`. Finally, if a parsed playlist contains more than one
distinct nonempty effective key URI across its segment list, the affected
surface is `mixed_generation`, even when the target fragment's own URI matches
its qualified key. These cross-claim checks participate in the surface reason
precedence below.

Boundary classifications are therefore unambiguous:

| Authenticated input condition | Required first reason |
| --- | --- |
| explicit `IV=0X` followed by 32 hex digits | `invalid_iv` |
| effective URI differs from the qualified catalog key URI | `uri_mismatch` |
| one surface's catalog rows disagree on key ID or generation | `mixed_generation` |
| a parsed playlist uses multiple effective key URIs | `mixed_generation` |
| parsed segment sequence differs from signed catalog sequence | `playlist_malformed` |
| contributing playlists disagree on media sequence | `playlist_malformed` |

The first matching surface reason is authoritative:

`absent`, `catalog_invalid`, `playlist_malformed`, `unsupported_method`,
`unknown_key`, `uri_mismatch`, `invalid_iv`, `mixed_generation`,
`cipher_digest_mismatch`, `cipher_length`, `decrypt_failed`, `padding_invalid`,
`plaintext_digest_mismatch`, `valid`.

Fragment rows preserve the catalog's sequence/path order and record their own
effective URI, lowercase 32-hex IV (without `0x`), digests, validity, and reason.
A surface is `valid` only when its complete declared fragment set is valid and
uses one key ID/generation. An absent or whole-catalog-invalid surface has null
key/generation/media sequence and an empty fragment array. Readable empty or
non-block-aligned bytes can reach `cipher_length` only when their actual digest
matches the signed catalog digest.

## Rendition state and global decision

Require exact canonical custody and evidence predecessors and recompute their
source/binding validity. Then classify every rendition:

- `old`: published current evidence is valid and no candidate artifact is
  visible or staged.
- `staged`: published current evidence and staged candidate evidence are valid,
  with no published candidate fragment.
- `advertised`: a published playlist exposes candidate key/generation but lacks
  a valid candidate fragment proof.
- `published`: published candidate evidence is valid.
- `broken`: required current evidence is invalid; a candidate artifact exists but
  fails proof; generations conflict; or none of the preceding states fits.

Candidate visibility is profile-global; media sequence, IV, and fragment proof
remain rendition-local. Sort classifications by rendition. Decide in this exact
order:

1. `quarantine` when custody is not ready, a predecessor is invalid, or any
   rendition is `broken` or `advertised`.
2. When at least one rendition is `published`, `finish_commit` only if every
   other rendition is `published` or `staged`; otherwise `quarantine`.
3. With no published candidate, all `staged` gives `commit`.
4. With no published candidate, a mix of `staged` and `old` gives
   `rollback_pending`.
5. All `old` gives `hold_current`.

`custody.ready=false` is an unconditional profile-wide quarantine. In
particular, any non-qualified candidate custody row (for example revoked,
expired, untrusted, or unwrappable) prevents `commit` even if every evidence
surface would otherwise classify as `staged`; emit quarantine actions for all
renditions and a disabled plan.

Actions, sorted by rendition, are:

| Decision/state | Action |
| --- | --- |
| any `quarantine` | `quarantine` for every rendition |
| `finish_commit` + `published` | `retain_candidate` |
| `finish_commit` + `staged` | `publish_candidate` |
| `commit` + `staged` | `publish_candidate` |
| `rollback_pending` + `staged` | `remove_staged` |
| `rollback_pending` + `old` | `retain_current` |
| `hold_current` + `old` | `retain_current` |

Only `commit` and `finish_commit` produce an enabled FFmpeg plan. All other
decisions produce the exact disabled-plan representation in the artifact
contract. Certificate hashing, confirmations, IV derivation, and plan binding
are specified there.

## Guardian trust and signed rollout ledger

Candidate publication additionally requires an authenticated rollout witness.
`guardian-trust.json` is a strict `cipherwave.guardian-trust.v2` object with
exactly `schema`, `checkpointPolicy`, and `guardians`. Its policy has exactly
`signatureThreshold`, `organizationThreshold`, `requiredCoverageMask`,
`minimumTrustWeight`, `coverageAfterOrganizationLoss`,
`minSelectedOrganizations`, and `maxSelectedPerOrganization`. All except the
mask are positive integers. `requiredCoverageMask` is exactly four lowercase
hexadecimal digits.

Guardians are sorted by unique `guardianId` and have exactly `guardianId`,
`organization`, `checkpointOperator`, `status`, `publicKey`, `notBeforeUnix`,
`notAfterUnix`, nullable `compromisedAtUnix`, `coverageMask`, and
`trustWeight`. IDs, organizations, and operators are ASCII tokens. Status is
`active` or `inactive`; coverage is four lowercase hexadecimal digits; trust
weight is a positive integer; public keys are 32-byte unpadded-base64url
Ed25519 keys. Validity is half-open. Approval records require their guardian to
be active and available at `audit_unix`.

`rollout-ledger.json` is a strict `cipherwave.rollout-ledger.v2` object with
exactly `schema`, `profileId`, `candidateGeneration`, `records`, and
`checkpoint`. Its profile and generation must name the active candidate. A
record has exactly:

```text
recordId, sequence, previousRecordSha256, approvalId, revision,
predecessorRecordId, guardianId, profileId, candidateGeneration,
operation, scopes, riskCost, signature
```

Sequence starts at zero and is contiguous. The first previous hash is 64 zeroes;
every later value is SHA-256 of canonical JSON of the complete preceding signed
record. A record signature is Ed25519 over
`"Cipherwave rollout record v1\0" || canonical_json(record without signature)`.
The named guardian must be available at the audit instant. Each approval starts
at revision 1 with a null predecessor. Every later revision is exactly one
higher, names the preceding head record, and keeps the same guardian. An
approval's unique final record is its operative head; earlier revisions never
remain independently eligible.

`operation` is `grant` or `revoke`. A grant has one or more unique scopes,
sorted by rendition then action, and a nonnegative integer `riskCost`. Each
scope has exactly `rendition` and `action`, where action is
`publish_candidate` or `retain_candidate`. A revoke has an empty scope array
and zero risk. Its approval is not eligible. A grant is also ineligible when
its profile or candidate generation differs from the active profile, or when
its scope set is empty or is not a subset of the requested rollout actions.

The checkpoint has exactly `treeSize`, `rootSha256`, `issuedAtUnix`, and sorted
`signatures`. It must cover every record and may not be issued after
`audit_unix`. Leaf hashes are
`SHA256(0x00 || canonical_record)` and parent hashes are
`SHA256(0x01 || left || right)`. At an odd level, carry the final node upward
unchanged; never duplicate it.

Each signature row has exactly `guardianId`, nonnegative integer
`signedAtUnix`, and a 64-byte unpadded-base64url `signature`. Rows are sorted by
guardian ID bytes, signed time, then signature bytes. Define the checkpoint core
as the exact object with schema `cipherwave.rollout-checkpoint.v2`, `profileId`,
`candidateGeneration`, `treeSize`, `rootSha256`, and `issuedAtUnix`. The Ed25519
signature input is:

`"Cipherwave rollout checkpoint v1\0" || canonical_json(core) || 0x00 || u64be(signedAtUnix)`

Classify every row in order. The first matching result is
`duplicate_guardian`, `unknown_guardian`, `guardian_inactive`,
`guardian_out_of_window`, `guardian_compromised`, `bad_signature`, or `valid`.
The first occurrence establishes duplicate tracking even if it is otherwise
invalid. Window and compromise checks use that row's `signedAtUnix`; a guardian
is compromised when `signedAtUnix >= compromisedAtUnix`. Only valid rows count.
Their distinct signer count and distinct `checkpointOperator` count must meet
the two checkpoint thresholds.

## Complete checkpoint frontier

Every valid endorsement becomes a candidate carrying its guardian ID,
checkpoint operator, numeric coverage mask, trust weight, and signing lag
`max(0, issuedAtUnix - signedAtUnix)`. A frontier witness selects at most one
candidate per checkpoint operator. Process operators in UTF-8 byte order. For
each operator, consider skipping it and then each of its candidates in guardian
ID byte order.

The state coordinate is `(coverage & requiredCoverageMask,
min(weight, minimumTrustWeight))`. At every coordinate retain exactly one
representative, minimizing in order: selected count, total signing lag,
negative uncapped total trust weight, then the bytewise-sorted guardian-ID
array. Coalescing happens after each operator. After the final operator, render
every reachable coordinate in ascending numeric `(coverage,cappedWeight)`
order. Computing only the qualifying coordinate, sampling, subset enumeration,
or greedily choosing high-coverage guardians is nonconforming. The qualifying
witness is the representative at `(requiredCoverageMask,
minimumTrustWeight)`; its absence is an authorization-integrity failure.

## Exact resilient authorization witness

First derive the proposed decision and actions from custody and HLS evidence.
Authorization is required exactly when that proposal is `commit` or
`finish_commit`; requested targets are its `publish_candidate` and
`retain_candidate` rendition/action pairs. Choose a subset of eligible approval
heads subject to all of these simultaneous constraints:

- at most one selected approval per guardian;
- at most `maxSelectedPerOrganization` approvals per organization;
- at least `minSelectedOrganizations` represented organizations; and
- for every requested target and every registered organization, removing all
  selected approvals from that organization leaves at least
  `coverageAfterOrganizationLoss` selected approvals that cover the target.

Among every feasible subset choose, in order: minimum total unrounded integer
`riskCost`, then minimum approval count, then the bytewise-lexicographically
smallest sorted approval-ID array. This is an exact global optimization; greedy
selection, per-target selection, or checking only organizations represented in
the selected subset is nonconforming. The supplied ledger deliberately makes
cheapest-row-first selection suboptimal.

If no witness exists for a required authorization, the final decision becomes
`quarantine`, all final actions become `quarantine`, and the FFmpeg plan is
disabled. The authorization proof still records the proposed decision and
requested targets, so this gate is non-circular. A non-publication proposal
does not require a witness and is ready with an empty selection.

The three similarly named structures are intentionally different. Certificate
core `renditions` contains `{rendition,state}` objects. FFmpeg plan-body
`renditions` is only the profile's string array. Authorization-proof requested
actions and coverage rows contain `{rendition,action}` values. Never substitute
one structure for another when computing certificateCoreSha256,
planBodySha256, authorizationSha256, or the final seal.

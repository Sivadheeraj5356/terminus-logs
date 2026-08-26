# Cipherwave artifact contract

This document enumerates every output field, type, order, null rule, and byte
binding. Objects accept and emit no extra fields. JSON integers are exact and
floating-point values are forbidden.

## Canonical bytes and source digests

For signing, hashing, HMAC, or an intermediate value, canonical JSON recursively
sorts object keys by their UTF-8 bytes, preserves array order, uses compact UTF-8
without ASCII escaping, and has no trailing LF. A JSON artifact is those bytes
followed by exactly one LF. Lowercase 64-hex denotes SHA-256 or HMAC-SHA256.

Source digests bind semantic inputs so harmless TOML or registry-manifest
layout cannot change an authorization:

- `profileSha256` is SHA-256 of canonical JSON of the exact semantic `Profile`
  object defined below, with no LF. It is not a hash of the TOML bytes and not
  a JSON transcription that preserves the TOML snake_case key names.
- `trustSha256` is SHA-256 of canonical JSON of the validated complete `Trust`
  value, with no LF.
- `catalogSha256` is SHA-256 of canonical JSON of the validated complete
  `Catalog` value including `signature`, with no LF.
- `registrySha256` is SHA-256 of
  `"Cipherwave registry digest v1\0"` followed by every value entry in the
  logical registry `keys` export in byte-lexicographic key order. Each decoded
  entry contributes a
  four-byte unsigned big-endian key length, key bytes, an eight-byte unsigned
  big-endian value length, and the exact value bytes.
- `guardianTrustSha256` and `rolloutLedgerSha256` hash canonical JSON of the
  complete validated authority, including keys and signatures, with no LF.
- `custodySha256`, `evidenceSha256`, `checkpointFrontierSha256`,
  `authorizationSha256`, and final `certificateSha256` hash complete
  artifact file bytes and therefore include their required final LF.

The semantic `Profile` object used only for `profileSha256` has exactly these
members and value mappings; no snake_case member or extra member is present:

| Canonical JSON member | Validated TOML value |
| --- | --- |
| `schema` | `schema` |
| `profileId` | `profile_id` |
| `auditUnix` | `audit_unix` |
| `currentKeyId` | `current_key_id` |
| `currentGeneration` | `current_generation` |
| `candidateKeyId` | `candidate_key_id` |
| `candidateGeneration` | `candidate_generation` |
| `renditions` | `renditions`, preserving the validated array order |
| `allowedKeyHosts` | `allowed_key_hosts`, preserving the validated array order |
| `trustedSpkiSha256` | `trusted_spki_sha256`, preserving the validated array order |
| `renderSegmentCount` | `render_segment_count` |

Canonical JSON sorting still applies after this mapping. Therefore the hash
preimage uses the camelCase members above even though `profile.toml` is written
with snake_case keys.

A predecessor is accepted only if it is strictly decoded, has no extra fields,
is canonical, has exactly one LF, names the current profile/audit, and carries
source digests equal to freshly recomputed current semantic inputs.

Atomic output means write a sibling temporary file, flush/close it, and rename
it over the requested path only after the complete artifact is available. A
failing command leaves no newly requested output or temporary sibling.

## Custody artifact

`custody.json` is one `cipherwave.custody.v1` object with exactly:

| Field | Type and rule |
| --- | --- |
| `schema` | string, exactly `cipherwave.custody.v1` |
| `profileId` | profile ID string |
| `auditUnix` | profile audit integer |
| `sources` | exact `CustodySources` object below |
| `ready` | boolean; true only when both key rows qualify |
| `keys` | exactly two `CustodyRow` objects, current then candidate |

`CustodySources` has exactly `profileSha256`, `registrySha256`, and
`trustSha256`, each lowercase 64-hex under the semantic rules above.

A `CustodyRow` has exactly:

| Field | Type and rule |
| --- | --- |
| `role` | `current` or `candidate` in that required row order |
| `keyId` | profile-requested key ID, including missing/malformed cases |
| `generation` | profile-requested generation integer |
| `qualified` | boolean; equivalent to `reason == "qualified"` |
| `reason` | one key-qualification reason in documented precedence |
| `keyUri` | qualified exact HTTPS URI string; otherwise null |
| `spkiSha256` | qualified lowercase 64-hex pin; otherwise null |
| `keyHandle` | qualified lowercase 64-hex HMAC handle; otherwise null |

No raw key, nonce, wrapped key, or record signature appears in this artifact.

## Evidence artifact

`evidence.json` is one `cipherwave.evidence.v1` object with exactly:

| Field | Type and rule |
| --- | --- |
| `schema` | string, exactly `cipherwave.evidence.v1` |
| `profileId` | profile ID string |
| `auditUnix` | profile audit integer |
| `sources` | exact `EvidenceSources` object below |
| `rows` | complete ordered array of `EvidenceRow` |

`EvidenceSources` has exactly `profileSha256`, `registrySha256`, `trustSha256`,
`catalogSha256`, and `custodySha256`. The final member hashes the complete exact
custody artifact bytes.

There are exactly `2 * len(profile.renditions)` evidence rows. Renditions use
profile order (already sorted); within each rendition, `published` precedes
`staged`. An `EvidenceRow` has exactly:

| Field | Type and rule |
| --- | --- |
| `rendition` | profile rendition string |
| `surface` | `published` or `staged` |
| `present` | true exactly when an authenticated catalog has at least one row for this rendition/surface |
| `valid` | boolean; true exactly for reason `valid` |
| `reason` | first matching encrypted-fragment surface reason |
| `keyId` | one uniform nonempty catalog key ID, otherwise null |
| `generation` | one uniform catalog generation, otherwise null |
| `mediaSequence` | parsed playlist media sequence, otherwise null |
| `fragments` | ordered `EvidenceFragment` array; empty for absent/no trusted rows |

`keyId` and `generation` are populated whenever authenticated nonempty catalog rows for the
surface agree, even if that key is unknown or the later proof fails. They are
null for absent, empty, or mixed-identity surfaces. `mediaSequence` is populated
only after the playlist parses. Fragment order is catalog sequence, then
playlist path and segment path by UTF-8 byte order.

An `EvidenceFragment` corresponds to one catalog row and has exactly:

| Field | Type and rule |
| --- | --- |
| `sequence` | catalog unsigned sequence integer |
| `playlistPath` | catalog relative path string |
| `segmentPath` | catalog relative path string |
| `keyUri` | effective parsed key URI string, otherwise null |
| `ivHex` | valid derived explicit/implicit IV as 32 lowercase hex, otherwise null |
| `ciphertextSha256` | actual readable ciphertext digest; empty string if unreadable |
| `plaintextSha256` | recovered plaintext digest after decrypt and strict padding; otherwise null |
| `valid` | boolean; true exactly for reason `valid` |
| `reason` | the fragment's first applicable encrypted-fragment reason |

Fragment reasons use the same documented vocabulary. Surface-level failures
that prevent trusted fragment construction (`absent`, `catalog_invalid`, or
`playlist_malformed`) may have an empty fragment array. Whole-catalog
signature/signer/schema/profile failure makes every row `present=false`,
`valid=false`, `catalog_invalid` with null metadata and an empty fragment array.
A structurally invalid, unsafe-path, duplicate, or out-of-order catalog row has
the same whole-catalog effect. Once the catalog itself authenticates, a claimed
surface with missing, unreadable, or symlink-escaping media is `present=true`
and `catalog_invalid`. A surface row's reason is the earliest applicable
surface failure under the published precedence; it
is `valid` only when its complete fragment array is nonempty and every fragment
is valid with one key identity.

## Authorization proof

`checkpoint-frontier.jsonl` is the complete final checkpoint frontier from the
security contract. Each row is recursively key-sorted compact ASCII JSON plus
one LF and has exactly `coverageMask`, `cappedWeight`, `guardianIds`,
`selectedCount`, `totalLag`, `totalWeight`, and `rowDigest`. Rows are ordered by
ascending numeric coverage mask then capped weight. `guardianIds` is bytewise
sorted. `rowDigest` is lowercase SHA-256 of canonical JSON of the preceding six
fields with no LF. The file has no blank lines and ends in exactly one LF.

The frontier `stateDigest` is SHA-256 of the concatenation of the raw 32-byte
row digests in file order. `frontierSha256` hashes the exact complete JSONL
bytes, including every LF.

`authorization-proof.json` is one canonical
`cipherwave.authorization-proof.v2` object with exactly these members:

| Field | Type and rule |
| --- | --- |
| `schema` | exact proof schema string |
| `profileId` | active profile ID |
| `auditUnix` | active audit integer |
| `candidateGeneration` | active candidate generation |
| `sources` | exact `AuthorizationSources` below |
| `proposedDecision` | decision before the rollout-authorization gate |
| `required` | true exactly for a proposed `commit` or `finish_commit` with requested targets |
| `ready` | true when authorization is not required or a feasible exact witness exists |
| `requestedActions` | sorted unique `{rendition,action}` target rows |
| `checkpoint` | authenticated checkpoint summary |
| `checkpointEndorsements` | one verdict per supplied signature row |
| `checkpointFrontier` | exact complete-frontier summary |
| `policy` | exact witness policy summary |
| `heads` | one ordered row per final approval-chain head |
| `selectedApprovalIds` | selected IDs in bytewise order |
| `selectedOrganizations` | represented organizations in bytewise order |
| `selectedCount` | exact selected ID count |
| `totalRisk` | sum of selected integer risk costs |
| `coverage` | one complete target coverage row per requested action |
| `selectionDigest` | digest defined below |
| `proofDigest` | digest defined below |

`AuthorizationSources` has exactly `guardianTrustSha256`,
`rolloutLedgerSha256`, `custodySha256`, `evidenceSha256`, and
`checkpointFrontierSha256`. The first two are semantic authority hashes; the
other three bind exact LF-terminated predecessor or frontier bytes.

`checkpoint` has exactly `treeSize`, `rootSha256`, `issuedAtUnix`,
`validSignerIds`, and `validOrganizations`; both arrays are sorted. `policy`
has exactly `requiredCoverageMask`, `minimumTrustWeight`,
`coverageAfterOrganizationLoss`, `minSelectedOrganizations`, and
`maxSelectedPerOrganization`.

Each `checkpointEndorsements` row has exactly `guardianId`, `signedAtUnix`,
`valid`, `reason`, `organization`, `coverageMask`, `trustWeight`, and
`lagSeconds`, preserving checkpoint row order. Reason is one of the seven
classification results in the security contract. The final four fields are
the validated checkpoint-operator string, four-digit mask, integer weight, and
integer lag for `valid`; all four are null otherwise.

`checkpointFrontier` has exactly `requiredCoverageMask`,
`minimumTrustWeight`, `stateCount`, `stateDigest`, `frontierSha256`, and
`selectedWitness`. The first five values bind the frontier contract.
`selectedWitness` is the complete JSONL row at the required coordinate and
therefore has the same exact seven fields, including its `rowDigest`.

Each `heads` row has exactly `approvalId`, `recordId`, `revision`, `guardianId`,
`organization`, `operation`, `reason`, `scopes`, `riskCost`, and
`recordSha256`. It is ordered by approval ID. `reason` is exactly one of
`operative`, `revoked`, `stale_profile`, `stale_generation`, or
`scope_mismatch`. Scopes retain their canonical authority representation.
`recordSha256` hashes canonical JSON of the complete signed head record.

Each `coverage` row has exactly `rendition`, `action`, `selectedApprovals`,
`organizationLoads`, and `survivorsAfterLoss`. Both organization arrays contain
every organization present in guardian trust in bytewise order.
`selectedApprovals` is an integer count of the selected approval records that
cover that exact rendition/action target; it is not an approval-ID array. The
selected identifiers are represented only by the proof's top-level
`selectedApprovalIds` array.
`organizationLoads` rows have exactly `organization` and `selected`;
`survivorsAfterLoss` rows have exactly `organization` and
`survivingApprovals`.

Define `selectionValue` as the object with exactly `requestedActions`,
`selectedApprovalIds`, `selectedOrganizations`, `totalRisk`, and `coverage`,
using the values rendered in the proof. `selectionDigest` is lowercase SHA-256
of canonical JSON of that object. `proofDigest` is lowercase SHA-256 of
canonical JSON of the complete proof object with only `proofDigest` omitted.
The written proof is canonical JSON plus one LF.

## Certificate core and classifications

The certificate core is not written as a separate file. Its canonical bytes are
the `cipherwave.rotation-core.v1` object with exactly:

```text
schema, profileId, auditUnix, sources, decision,
currentKey, candidateKey, renditions, actions
```

`sources` is `CertificateSources`, exactly `custodySha256`, `evidenceSha256`,
and `authorizationSha256`, each over the complete LF-terminated predecessor
artifact.

A non-null `currentKey` or `candidateKey` is a `KeyReference` with exactly
`keyId`, `generation`, `keyUri`, `spkiSha256`, and `keyHandle`, copied from the
corresponding qualified custody row. An unavailable/unqualified role is null.

`renditions` contains one object per profile rendition, sorted by rendition,
with exactly `rendition` and `state`; state is `old`, `staged`, `advertised`,
`published`, or `broken`. `actions` has the same complete rendition order and
each object has exactly `rendition` and `action`; actions are
`quarantine`, `retain_candidate`, `publish_candidate`, `remove_staged`, or
`retain_current` as allowed by the security matrix.

Define:

```text
coreBytes = canonical_json(certificate_core)
certificateCoreSha256 = lowerhex(SHA256(coreBytes))
```

## FFmpeg plan body and IV

The plan body is not written as JSON. It is the exact `FFmpegPlanBody` value used
for binding, with these JSON field names and types:

| Field | Type and rule |
| --- | --- |
| `schema` | `cipherwave.ffmpeg-plan.v1` |
| `profileId` | profile ID string |
| `decision` | final decision string |
| `enabled` | true only for `commit` or `finish_commit` |
| `certificateCoreSha256` | lowercase digest defined above |
| `keyId` | enabled candidate key ID; disabled empty string |
| `generation` | enabled candidate generation; disabled zero |
| `keyUri` | enabled candidate HTTPS URI; disabled empty string |
| `spkiSha256` | enabled candidate pin; disabled empty string |
| `ivHex` | enabled 32-lowercase-hex IV; disabled empty string |
| `renderSegmentCount` | profile render count for enabled and disabled plans |
| `renditions` | complete profile rendition array in profile order |
| `actions` | complete certificate action array |

For an enabled plan:

```text
ivBytes = first_16_bytes(HMAC-SHA256(
  key = unwrapped candidate content key,
  data = "Cipherwave plan IV v1\0" || coreBytes
))
ivHex = lowerhex(ivBytes)
```

Define `planBodySha256` as lowercase SHA-256 over canonical JSON of this complete
body with no LF. Only `certificateSha256` is absent from the body.

## Rotation certificate

`rotation-certificate.json` is one `cipherwave.rotation-certificate.v1` object
with exactly:

| Field | Type and rule |
| --- | --- |
| `schema` | exact certificate schema string |
| `profileId` | profile ID string |
| `auditUnix` | profile audit integer |
| `sources` | exact `CertificateSources` object |
| `decision` | `quarantine`, `finish_commit`, `commit`, `rollback_pending`, or `hold_current` |
| `currentKey` | qualified current `KeyReference`, otherwise null |
| `candidateKey` | qualified candidate `KeyReference`, otherwise null |
| `renditions` | complete ordered classification array |
| `actions` | complete ordered action array |
| `planBodySha256` | digest of the exact plan body above |
| `keyConfirmations` | exact object with `current` and `candidate` |
| `seal` | final certificate seal |

Each available key confirmation is:

```text
lowerhex(HMAC-SHA256(
  key = that role's unwrapped 16-byte key,
  data = "Cipherwave certificate confirmation v1\0" || coreBytes
))
```

An unavailable role has a null confirmation. The unsealed certificate contains
every certificate member except `seal`, retaining `planBodySha256` and both
confirmations. The final seal is:

```text
lowerhex(SHA256(
  "Cipherwave rotation certificate v1\0" || canonical_json(unsealed_certificate)
))
```

The written certificate is canonical JSON plus one LF.

## Final TOML plan

`ffmpeg-plan.toml` contains the plan body plus
`certificate_sha256 = lowerhex(SHA256(complete_certificate_artifact_bytes))`.
The digest therefore includes the certificate's one LF. It is added after the
certificate exists and is deliberately excluded from `planBodySha256`, avoiding
a circular dependency.

The supplied renderer writes UTF-8 in this fixed scalar order:

```text
schema
profile_id
decision
enabled
certificate_core_sha256
certificate_sha256
key_id
generation
key_uri
spki_sha256
iv_hex
render_segment_count
renditions
```

It then writes one `[[actions]]` table per action in array order, containing
`rendition` then `action`. ASCII strings use TOML basic-string escaping
equivalent to JSON quoting, booleans are lowercase, integers are base-10 without leading zeroes,
and renditions use exactly an inline array such as `["audio", "video"]` with a
comma and one space. Action blocks immediately follow the renditions line. The
file has no comments or blank lines and ends with exactly one LF.

## Validation and exit behavior

Strict artifact readers reject missing/extra fields, duplicate object keys,
wrong primitive types, floats, unknown enum values, incorrect row universes,
incorrect order, noncanonical bytes, or anything other than one final LF.
Malformed inputs/flags exit 2. Bad authentication, integrity, source/predecessor
binding, confirmation, seal, or authorization exits 3. Security denials created
from otherwise valid inputs are artifacts and exit zero.

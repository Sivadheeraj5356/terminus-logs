# Cipherwave contract map

The incident packet is derived from seven immutable authority surfaces:

| Authority | Location | Governs |
| --- | --- | --- |
| rotation profile | `/app/fixtures/visible/profile.toml` | audit time, requested keys, generations, rendition universe, trust constraints |
| key registry export | `/app/fixtures/visible/registry.json` | exact signed and wrapped current/candidate key-record bytes |
| trust document | `/app/fixtures/visible/trust.json` | issuer eras, Ed25519 public keys, AES-GCM KEK, catalog signer |
| signed catalog | `/app/fixtures/visible/catalog.json` | expected playlists, segments, sequences, generations, and ciphertext/plaintext digests |
| media tree | `/app/fixtures/visible/media` | HLS declarations and encrypted fragment bytes |
| guardian trust | `/app/fixtures/visible/guardian-trust.json` | approval organizations, checkpoint operators, Ed25519 keys, lifecycle, coverage, weight, quorum, and resilience policy |
| rollout ledger | `/app/fixtures/visible/rollout-ledger.json` | signed approval amendments, revocations, hash chain, Merkle checkpoint endorsements, scopes, and risk costs |

`security-contract.md` defines how those authorities are authenticated and reconciled. `artifact-contract.md` defines the exact six output byte streams and every cross-artifact binding.

## Trust boundaries

- Every input remains untrusted until its relevant schema, signature, era, path, and cryptographic binding is validated.
- The profile's `audit_unix` is the sole time authority.
- No network service, wall clock, environment variable, or bundled output is an authority.
- Qualified content keys may exist only in memory while deriving the packet; serialization and printing are prohibited.
- An earlier artifact is trusted by a later phase only after strict byte canonicality and freshly recomputed source bindings are confirmed.

## Registry export bytes

The registry is a transport-neutral export of the original logical bucket. `registry.json` has exactly `bucket` and `entries`. `bucket` must equal `keys`. `entries` is ordered by `key` in UTF-8 byte order and contains unique objects with exactly `key` and `valueBase64`. Each `key` is the lookup key and each `valueBase64` is standard padded base64 encoding of the exact key-record JSON bytes. The key-record contract applies to those decoded value bytes. The registry semantic digest is defined over the decoded lookup-key/value-byte pairs, not over the manifest's JSON formatting.

## Deliverable boundary

Only `/app/out/cipherwave-incident/custody.json`, `evidence.json`,
`checkpoint-frontier.jsonl`, `authorization-proof.json`,
`rotation-certificate.json`, and `ffmpeg-plan.toml` are deliverables. Helper
code, decoded keys, intermediate
plaintext, and temporary siblings are outside that directory's accepted contents.

At completion, retained paths under `/app/out` and `/tmp` are part of the
confidentiality boundary, not merely the six deliverables. No regular-file content,
directory or file name, or symlink target in those trees may contain either unwrapped
16-byte content key as raw bytes, lowercase or uppercase hexadecimal, standard or
URL-safe Base64 (padded or unpadded), Base32 (padded or unpadded), Ascii85, Base85,
or percent-encoded bytes. Temporary custody material must be removed before the
ruling completes; changing its name or encoding does not make it acceptable.

# Site profile (opaque)

`--profile` names a little-endian binary **site profile** that selects
multi-fault check order, which octets count as header OWS for edge trim, and
content-digest framing. Agents must not hard-code RFC Message Signatures /
RFC 9110 OWS / Digest defaults — the profile is authoritative for this
deployment.

## On-disk encoding

The profile is a **fixed-length** little-endian blob that begins with the
ASCII magic `HRMP`. Exact field sizes and offsets are **not** restated here —
recover the packing by hex-dumping `/app/data/site.profile` and checking the
known outcomes under `/app/fixtures/gold/`.

Any other layout (bad magic/version/flags, wrong order length, order not a
permutation of `1..6`, unknown `digest_mode`, reserved bits set) is
`profile_invalid`. A missing or non-regular `--profile` path is `io` (after
CLI `usage` checks).

Semantic fields carried by the blob (once unpacked):

- a permutation of check-order reason codes `1..6`
- an `ows_mask` bitfield for header edge trim
- a `digest_mode` selector for content-digest framing

The shipped sample uses order `1..6`, SP|HTAB OWS, and colon-framed standard
base64 digest mode — confirm by decoding the sample, not by assuming RFC
defaults.

## Check-order reason codes

| Byte | Reason group |
|------|----------------|
| 1 | `unknown_kid` |
| 2 | time: `invalid_window`, else `not_yet_valid`, else `expired` |
| 3 | `missing_covered_header` |
| 4 | `bad_digest` |
| 5 | `bad_mac` |
| 6 | `replay` |

CLI/`usage` and envelope/keyring/`profile` load failures still win **before**
any profile-ordered domain check. Among domain faults that are active for the
envelope, walk `order` left-to-right and emit the first hit.

`replay` is active only when the MAC compares equal (a bad MAC with a seen hit
is still `bad_mac` when code `5` is evaluated — do not treat replay as active
on MAC failure). `bad_digest` is active only when `content-digest` is covered
and the trimmed header value disagrees with the profile-framed token.

## OWS mask bits

Edge trim removes a run of octets whose bit is set in `ows_mask`:

| Bit | Octet |
|-----|-------|
| 0 | SP (`0x20`) |
| 1 | HTAB (`0x09`) |
| 2 | NBSP (`U+00A0`, UTF-8 `C2 A0`) |

Bits outside `0..2` must be zero or the profile is `profile_invalid`. Interior
octets are never collapsed. Sample SP|HTAB trim leaves NBSP edges in the MAC
material. An SP-only mask leaves HTAB edges in the MAC material. A mask with
all three bits also trims NBSP edges.

## Digest modes

| Mode | Token form |
|------|------------|
| 0 | `sha-256=` + `:` + standard-base64(digest) + `:` |
| 1 | `sha-256=` + standard-base64(digest) (no surrounding colons) |
| 2 | `sha-256=` + `:` + base64url-nopad(digest) + `:` |

The `CONTENT_DIGEST` canonical line and the success-line `digest=` field both
use this profile framing. MAC input bytes therefore change with `digest_mode`.

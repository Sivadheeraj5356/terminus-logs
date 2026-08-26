# Content digest and MAC

## Content digest

SHA-256 over the raw body bytes (empty body is valid). Emit the token using
the `--profile` `digest_mode` (see `profile.md`):

| Mode | Form |
|------|------|
| 0 | `sha-256=` + `:` + standard-base64(digest) + `:` |
| 1 | `sha-256=` + standard-base64(digest) (no surrounding colons) |
| 2 | `sha-256=` + `:` + base64url-nopad(digest) + `:` |

Standard base64 uses the `A–Z a–z 0–9 + /` alphabet with `=` padding when
needed. Mode `2` uses the URL-safe alphabet **without** padding. No spaces
inside the token. No other algorithm label is valid for v1.

The `CONTENT_DIGEST` line of the canonical request is always this
profile-framed computed token.

## Covered `content-digest` (`bad_digest`)

When `content-digest` appears in `covered`, resolve the header value with the
same profile OWS edge trim as other covered headers and compare it to the
computed token above. If they differ, fail `bad_digest`.

This check is a domain fault ordered by `--profile` (sample profile places it
after time / missing-header and before `bad_mac`). A wrong covered
content-digest plus a wrong MAC still reports whichever of `bad_digest` /
`bad_mac` appears first in the profile order.

## MAC

```text
mac = base64url_nopad(HMAC-SHA256(key, profile_bound_message))
```

The HMAC message is **profile-bound**: the raw bytes of the active `--profile`
file are mixed with the canonical request before HMAC. Do **not** MAC the
canonical request alone (RFC-style `HMAC(key, CR)` fails the gold vectors).

Recover the exact mix (`profile` bytes, separator, then CR) from
`/app/fixtures/gold/` — known envelopes, profiles, and MACs under the shipped
site profile and mutated profiles.

Use the URL-safe base64 alphabet **without** padding. Padded or otherwise
non-canonical MAC encodings → `bad_mac`.

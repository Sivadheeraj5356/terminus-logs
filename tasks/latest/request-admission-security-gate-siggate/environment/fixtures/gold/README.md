# Site security attestation vectors

Published admit/deny vectors for this deployment's authentication gate.
Use them to recover how the site security profile binds into HMAC verification
(forgeries that MAC the canonical request alone must fail).

## Site profile (`/app/data/site.profile`)

Default profile bytes (length **17**):

```
hex: 48524d5001000000060102030405060300
```

Magic `HRMP`, then version/flags/count, order `1..6`, ows_mask, digest_mode.

## Profile-bound MAC mix

HMAC-SHA256 with the keyring key for `kid`.

Message bytes:

```
profile_bytes || 0x00 || CR
```

where CR is the UTF-8 canonical request under that profile's OWS mask and
digest mode. Bare `HMAC(key, CR)` is a forgery and must be denied.

## Worked example (site-default-happy)

| Piece | Value |
|-------|-------|
| profile hex | 48524d5001000000060102030405060300 |
| profile length | 17 |
| CR length (UTF-8) | 191 |
| HMAC message length | 209 = 17 + 1 + 191 |
| expected mac | 3mKd9gTyj9kTWWXSeOLF-IZeWmL6uGZihAofENQx7Rk |

## cases.json

Each entry: profile_hex, envelope path, expected_mac — site default, SP-only
OWS, and bare digest framing.

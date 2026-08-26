# Policy-bind contract

Path: /app/state/policy-bind.json
schema: reelseal.policy-bind/v1

| Field | Type | Rule |
|-------|------|------|
| schema | string | reelseal.policy-bind/v1 |
| engine | string | reelseal-runtime/v1 |
| profile_id | string | from roster (default reel-std) |
| key_id | string | from Gin /v1/keys/issue |
| key_urn | string | urn:reelseal:key:<key_id> |
| signing_alg | string | from resolve |
| allowed_algs | string[] | from resolve |
| profile_epoch | int | must match roster epoch |
| media_digest | string | from fetch receipt |
| policy_digest | string | see digest rule below |

Forbidden fields: key_uri, key_url.

## policy_digest serialization

`policy_digest` is the lowercase hex SHA-256 of the UTF-8 bytes of a **canonical JSON object** that contains **exactly these nine fields** and no others:

1. `allowed_algs`
2. `engine`
3. `key_id`
4. `key_urn`
5. `media_digest`
6. `profile_epoch`
7. `profile_id`
8. `schema`
9. `signing_alg`

Serialization rules:

- Object keys must be sorted lexicographically ascending.
- Separators must be compact: `,` between members and `:` between key and value, with no ASCII spaces.
- Do not include `policy_digest`, `key_uri`, or `key_url` in the hashed object.
- `profile_epoch` is a JSON number (integer); `allowed_algs` is a JSON array preserving resolve order.

Environment REELSEAL_API selects the Gin base URL (default http://127.0.0.1:8742).

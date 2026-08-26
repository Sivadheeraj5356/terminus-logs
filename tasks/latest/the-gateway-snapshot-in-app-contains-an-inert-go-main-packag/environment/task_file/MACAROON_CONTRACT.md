# Delegated macaroon audit contract

## Input, state, and normalization

`/app/input/inspection.json` is a JSON object with `evaluation_time`, `max_skew_seconds`, `root_keys`, `discharge_keys`, `revoked_identifiers`, `reserved_nonces`, `spent_discharges`, and `requests`. Times are Unix seconds encoded as JSON integers and must be handled as signed 64-bit integers. All input is structurally well formed. Key ids are unique in their respective key arrays; initial state arrays contain no duplicate identities.

A root key has `id`, `secret`, `not_before`, and `not_after`. A discharge key has `location`, `key_id`, `secret`, `not_before`, and `not_after`; its identity is `(location, key_id)`. Key windows are inclusive and checked against the request `timestamp`. Revocation is by exact macaroon or discharge identifier.

An initial reserved nonce is `{ "identifier": string, "nonce": string }`. An initial spent discharge is `{ "location": string, "key_id": string, "replay_id": string }`. Array order is persistent state order and is preserved in the final report.

A request has `id`, `timestamp`, `method`, `path`, `ip`, `scopes`, `body`, `nonce`, `macaroon`, and `discharges`. `scopes` is an array of strings. Its macaroon has `identifier`, `location`, `root_key_id`, `caveats`, and `signature`. Each discharge has `instance_id`, `replay_id`, `identifier`, `location`, `key_id`, `caveats`, `signature`, `binding`, and `attachment`. Discharge `instance_id` values are unique within one request. Replay ids need not be unique: the persistent discharge identity is `(location, key_id, replay_id)`.

Normalize a request as follows. Uppercase the method. Normalize the path by adding a leading slash, collapsing repeated slashes, removing `.` segments, applying `..` without moving above root, and removing the trailing slash except for `/`. Parse the IP as either IPv4 or IPv6 and render its canonical address string. Sort a copy of `scopes` ascending without removing duplicates. `body_sha256` is lowercase hexadecimal SHA-256 of the UTF-8 bytes of `body`.

Every caveat has `type`. The remaining fields and canonical payloads are:

| type | fields | canonical payload |
| --- | --- | --- |
| `time_before` | integer `value` | `time_before|<decimal value>` |
| `time_after` | integer `value` | `time_after|<decimal value>` |
| `method` | string `value` | `method|<uppercased value>` |
| `path_prefix` | string `value` | `path_prefix|<normalized value>` |
| `ip_cidr` | string `value` | `ip_cidr|<masked canonical CIDR>` |
| `scope` | string `value` | `scope|<value>` |
| `body_sha256` | string `value` | `body_sha256|<lowercased value>` |
| `third_party` | `caveat_id`, `location`, `key_id` strings | `third_party|<caveat_id>|<location>|<key_id>` |
| `third_party_quorum` | string `caveat_id`, integer `threshold`, ordered `authorities` | `third_party_quorum|<caveat_id>|<threshold>|<location1>|<key_id1>|...` |

Each quorum authority is `{ "location": string, "key_id": string }`. Authority pairs in one caveat are distinct and `1 <= threshold <= len(authorities)`. Their stored order is signed; do not sort them. Caveats are signed, evaluated, and traversed in stored order. The report includes the canonical payload of every primary caveat, including both third-party types.

## Signatures, primary bindings, and attachments

HMAC below means HMAC-SHA256. Strings are UTF-8. A primary signature starts as `HMAC(root secret, "M1\n" + location + "\n" + identifier + "\n" + root_key_id)`. For every caveat in stored order, replace the current 32-byte signature with `HMAC(current signature bytes, canonical caveat payload)`. Encode the final signature as exactly 64 lowercase hexadecimal characters.

A discharge signature uses the same caveat chaining, starting as `HMAC(discharge secret, "D1\n" + location + "\n" + identifier + "\n" + key_id + "\n" + replay_id)`. Its primary `binding` is lowercase hex `HMAC(bytes decoded from the supplied primary signature, bytes decoded from the supplied discharge signature)`. Binding is local evidence that the discharge belongs to this primary proof.

Its `attachment` proves the exact edge where it may be selected. For a discharge selected by caveat `C` stored on parent token `P`, the expected value is:

```
HMAC(bytes decoded from P.signature,
     UTF-8(canonical payload of C) || one zero byte || bytes decoded from discharge.signature)
```

The primary token's supplied signature is the parent signature for a primary caveat; a discharge token's supplied signature is the parent signature for its nested caveats. Every member selected for one quorum caveat uses that same caveat payload and parent signature. Attachments are deliberately not a local-audit reason because their intended edge is learned only during assignment.

A malformed uppercase, non-hex, or non-64-character signature, binding, or attachment never compares equal. Signature comparisons use the supplied strings only after strict decoding.

## First-party caveats

Evaluate first-party caveats independently and additively:

- `time_before` requires `timestamp < value`; `time_after` requires `timestamp >= value`.
- `method` requires the normalized request method to equal the uppercased caveat value.
- `path_prefix` requires the normalized path to equal the normalized prefix or start with that prefix followed by `/`; prefix `/` covers every path.
- `ip_cidr` requires the request IP to be inside the parsed CIDR.
- Each `scope` caveat independently has to cover every requested scope. `*` covers all scopes; a value ending in `:*` covers scopes beginning with the part through `:`, and any other value covers only itself. An empty request scope array passes every scope caveat.
- `body_sha256` requires the normalized body digest to equal the lowercased caveat value.

`first_party_unsatisfied` is emitted once if one or more first-party caveats on that token fail. Neither third-party type is a first-party caveat.

## Local discharge audit

Audit every supplied discharge locally, in input order, whether or not it is ultimately selected. Its local reasons are additive and sorted in this order: `unknown_discharge_key`, `discharge_key_inactive`, `revoked_identifier`, `replayed_discharge`, `bad_discharge_signature`, `bad_binding`, `first_party_unsatisfied`.

- Signature checking runs only when its discharge key is known.
- `replayed_discharge` is present when its persistent identity was already in spent state before this request. Discharges selected earlier in the same request are handled by assignment, not retroactively added to local results.
- Binding checking does not short-circuit: compare the supplied primary and discharge signature bytes whenever both are strict lowercase 32-byte hex values.
- First-party caveats are always evaluated.

A discharge is locally `usable` only when its local reason array is empty. Attachment is checked separately for each candidate proof edge.

## Complete proof-tree assignment

Assignment starts with both third-party caveat types on the primary, carrying the primary's supplied signature as their parent signature. It tracks supplied instance indexes, persistent discharge identities, and traversal output independently.

A `third_party` caveat selects one locally usable discharge only when:

- its instance is not already selected;
- its persistent discharge identity is not already selected in this request;
- identifier, location, and key id equal the caveat fields; and
- its attachment matches this exact parent signature and caveat.

Selecting it consumes its instance and persistent identity, appends `instance_id` to the traversal, and immediately visits its nested third-party caveats depth-first in stored order using its supplied signature as their parent signature. It then returns to the remaining caveats of its parent.

A `third_party_quorum` caveat selects exactly `threshold` locally usable discharges. Every member must have the caveat identifier, an authority pair listed by the caveat, a matching attachment, and an unselected instance and persistent identity. Selected members must use distinct authority pairs. Treat a quorum choice as follows:

1. Sort its members by `instance_id` and append all their instance ids contiguously to the traversal.
2. Consume all member instances, persistent identities, and authority pairs together.
3. Visit the selected members' nested caveats depth-first in that member order, then resume the parent's remaining caveats.

Consider every possible simple candidate and quorum combination, not merely the first match. A partial assignment succeeds when every third-party caveat reached from the primary is satisfied; supplied discharges may remain unused. A complete assignment is a successful partial assignment that selects every supplied discharge instance exactly once. Persistent-identity uniqueness still applies, so two supplied instances with one identity can never both belong to a complete assignment.

Among all successful assignments of either kind, compare complete `used_discharges` arrays lexicographically and choose the smallest. This compares the full final traversal, not a local candidate or quorum tuple. If no partial assignment exists, emit `third_party_unsatisfied`. If no complete assignment exists, emit `unused_discharge`; both occur when neither kind exists. Report the best complete assignment when one exists, otherwise the best partial assignment, otherwise `[]`.

## Stateful request decision

Evaluate requests in input order. A primary is authenticated when its root key is known and its supplied signature equals the expected signature. Key inactivity and revocation do not change whether a correct signature authenticates it.

The nonce replay identity is `(macaroon identifier, nonce)`. Immediately reserve it for every authenticated primary, even if it was already reserved or the request is later denied. Emit `replayed_nonce` when it was present before this request. Unknown-key and bad-signature requests neither test nor reserve nonce state.

After assignment for an authenticated primary, append every newly selected persistent discharge identity to spent state in `used_discharges` traversal order. This applies to the chosen complete or partial assignment even when another primary reason denies the request. Existing identities are never appended twice. Bad or unknown primaries do not perform assignment and spend no discharge.

Primary reasons are additive and sorted exactly as follows: `unknown_root_key`, `root_key_inactive`, `revoked_identifier`, `bad_primary_signature`, `timestamp_skew`, `replayed_nonce`, `first_party_unsatisfied`, `third_party_unsatisfied`, `unused_discharge`.

- Emit `unknown_root_key` when no root key matches. Emit `bad_primary_signature` only when the root key is known and the primary signature differs.
- Root-key activity and primary revocation are checked whenever applicable and do not gate signature verification.
- Emit `timestamp_skew` when `abs(evaluation_time - timestamp) > max_skew_seconds`, computing without signed overflow. This applies even to an unknown root key.
- Primary first-party and assignment reasons are emitted only for an authenticated primary. They remain additive when the root is inactive, identifier revoked, timestamp skewed, or nonce replayed.

The decision is `allow` only when the primary reason list is empty; otherwise it is `deny`.

## Exact report

Replace `/app/output/report.json` on every run. It is one object with exactly `evaluated_at`, `decisions`, `summary`, and `final_state`. `evaluated_at` equals input `evaluation_time`; decisions follow request order.

Each decision has exactly:

- `id`, copied from the request;
- `decision`, `allow` or `deny`;
- `reasons`, in primary reason order;
- `normalized`, with exactly `method`, `path`, `ip`, `scopes`, and `body_sha256`;
- `primary_caveats`, canonical payload strings in stored order;
- `used_discharges`, as defined by assignment;
- `discharge_results`, in supplied order, each with exactly `instance_id`, Boolean `usable`, and local `reasons`.

`summary` has exactly `allowed`, `denied`, and `reason_counts`. Count every primary reason, including multiple reasons on one request. Include only reasons that occurred.

`final_state` has exactly `reserved_nonces` and `spent_discharges`, using the same object shapes as input state. Preserve initial order, then append newly reserved or spent identities in their specified order. Arrays remain arrays when empty. JSON object member order is insignificant; array order and strings are exact.

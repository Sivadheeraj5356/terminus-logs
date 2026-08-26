# msgsigward security specification

This is the authoritative contract for the `msgsig.Verify` decision — the exact
behavior a correct verifier must exhibit. It defines a faithful subset of
**RFC 9421 (HTTP Message Signatures)** verification together with the acceptance
policy an HTTP verifier must enforce over a request that may carry **several**
offered signatures. A shipped verifier is correct only if, for every bundle, its
decision matches the decision this specification requires.

The evidence is immutable. `Verify` reads one bundle and returns a decision; it
never mutates the request, and it never trusts a field the signature did not
authenticate.

## 1. Input

```json
{
  "keys": {
    "<keyid>": { "alg": "ed25519",     "public": "<hex-32-bytes>" },
    "<keyid>": { "alg": "hmac-sha256", "secret": "<hex-bytes>" }
  },
  "now": 1700000000,
  "message": {
    "method":    "POST",
    "authority": "svc.example.com",
    "path":      "/api/v1/orders",
    "query":     "page=1&sort=asc",
    "headers": {
      "content-type":    "application/json",
      "content-digest":  "sha-256=:<base64>:",
      "x-fwd":           ["10.0.0.7", "10.0.0.9"],
      "signature-input": "sig1=(\"@method\" \"@authority\" \"@path\");created=..;keyid=\"k1\";alg=\"ed25519\"",
      "signature":       "sig1=:<base64-signature>:"
    },
    "body": "<raw request body, may be empty>"
  }
}
```

- `keys` maps a `keyid` to its trusted key. `alg` is the algorithm **bound** to
  that key. ed25519 keys carry a hex `public` (32 bytes); hmac-sha256 keys carry a
  hex `secret`.
- `now` is the fixed evaluation time (unix seconds) used for freshness.
- `message.query` is the raw query string **without** a leading `?` (`""` when
  there is no query). Header names are lowercase.
- A header value is **either a JSON string** (one field line) **or a JSON array
  of strings** (the same field name delivered on several lines, in order).
  `message.body` is the raw body bytes as a string.

## 2. Component identifiers and their values

A covered component is a name with zero or more **parameters**. Its serialised
identifier is the name as a Structured-Field string — a double-quoted string with
`\` and `"` backslash-escaped — followed, for each parameter in order, by `;name`
for a bare (boolean-true) parameter or `;name="value"` for a string parameter
(e.g. `"@method"`, `"@query-param";name="region"`, `"x-fwd";bs`). Each identifier
resolves to a **value**:

| Identifier                     | Value                                                                 |
|--------------------------------|-----------------------------------------------------------------------|
| `@method`                      | `message.method`, verbatim                                            |
| `@authority`                   | `message.authority`, **lowercased**, with a trailing `:443` port removed |
| `@path`                        | `message.path`, verbatim, except an empty path is `/`                |
| `@query`                       | `"?"` concatenated with `message.query`                              |
| `@query-param` `;name="n"`     | percent-decoded value of the one query parameter whose percent-decoded name equals `n` (see §2.1) |
| `<header>` (plain)             | the header's combined field value (see §2.2)                         |
| `<header>` `;bs`               | each field line byte-sequence-wrapped, joined with `, ` (see §2.2)   |
| `<header>` `;sf`               | the combined field value parsed as an RFC 8941 Dictionary and re-serialised in canonical form (see §2.3) |

Any other identifier — an unsupported derived component (`@status`, `@scheme`,
`@target-uri`, …), a header parameter other than `;bs` or `;sf` (and `;bs`/`;sf`
are mutually exclusive on one component), `@query-param` without a resolvable
single match, or a header name not present in `message.headers` — is
**unresolvable**: the bundle cannot be evaluated (see §8).

### 2.1 Percent-decoding

`%XX` (two hexadecimal digits, either case) decodes to that byte; `+` is a
literal plus sign; a `%` not followed by two hex digits is a literal `%`. For
`@query-param`, split `message.query` on `&`, split each element on the first `=`
into name and value (a missing `=` means an empty value), and compare
percent-decoded names. Exactly one parameter must match `n`; if the query is
empty or zero/multiple parameters match, the component is unresolvable.

### 2.2 Header field values

Collect the header's field lines (a JSON array contributes one line per element in
order; a JSON string contributes a single line). For each line: replace any
obsolete line folding — a line break followed by one or more spaces or tabs — with
a single space, then strip leading and trailing spaces and tabs.

- **plain**: join the resulting lines with `, ` (comma, space).
- **`;bs`**: encode each resulting line's bytes as a Structured-Field Byte
  Sequence — `:` + base64(line) + `:` — and join those with `, `.
- **`;sf`**: take the plain combined value and re-serialise it as a canonical
  RFC 8941 Dictionary (see §2.3).

### 2.3 Strict structured-field (`;sf`) canonicalisation

A `;sf` header's plain combined value is parsed as an RFC 8941 **Dictionary** and
re-serialised in canonical form. In this contract a Dictionary is a comma-separated
sequence of members `key` or `key=value`, each with zero or more parameters
`;pkey` or `;pkey=pvalue`. A `key`/`pkey` is `lcalpha`/`*` then any of
`lcalpha DIGIT _ - . *`. A bare `key` (no `=value`) has the Boolean value true.
Values and parameter values are **bare items** of one of four types:

- **Integer** — optional `-` then 1–15 digits (no decimal point).
- **String** — `"`…`"` with `\` and `"` backslash-escaped, printable ASCII only.
- **Token** — `ALPHA`/`*` then `tchar`/`:`/`/`.
- **Boolean** — `?1` (true) or `?0` (false).

Parsing tolerates optional spaces/tabs after each `,` and leading spaces/tabs;
canonical **serialisation** is exact and normalises every non-canonical form:

- members joined with exactly `, `; parameters as `;pkey` (Boolean-true) or
  `;pkey=<bare>`; a member/parameter whose value is Boolean **true** is written
  as just the key with **no** `=?1`;
- **Integer** serialised in the shortest decimal form (no leading zeros, e.g.
  `007`→`7`, `-03`→`-3`); **Boolean** as `?1`/`?0`; **Token** verbatim; **String**
  re-quoted with `\` and `"` escaped.

A value that does not parse under this grammar makes the bundle unevaluatable
(§8). For example, the field value `a=007,  b=widget, flag=?1;fresh=?1`
canonicalises to `a=7, b=widget, flag;fresh`.

## 3. Signature base

The signature base for one signature is the byte string built from its covered
components in **declared order**, one line each, followed by the trailing
`@signature-params` line. For each covered component, emit its serialised
identifier (§2), then `: ` (colon, space), then its value, then a single `\n`.
The final line (with **no** trailing newline) is:

```
"@signature-params": <member-value>
```

where `<member-value>` is the exact `(<components>)<params>` text of that
signature's member in the `Signature-Input` dictionary (§4), used **verbatim**
(the verifier does not re-serialise it).

### Worked example (one signature)

For the `Signature-Input` member value

```
("@method" "@authority" "@path" "@query-param";name="region" "x-fwd";bs);created=1700000000;keyid="edkey";alg="ed25519"
```

over a `POST` request with authority `API.Svc.Example.COM:443`, path `/orders`,
query `region=us-east&user=al%20ice`, and header `x-fwd` delivered as
`["  10.0.0.7 ", "10.0.0.9"]`, the signature base is exactly these bytes (`\n`
shown as line breaks; no trailing newline after the last line):

```
"@method": POST
"@authority": api.svc.example.com
"@path": /orders
"@query-param";name="region": us-east
"x-fwd";bs: :MTAuMC4wLjc=:, :MTAuMC4wLjk=:
"@signature-params": ("@method" "@authority" "@path" "@query-param";name="region" "x-fwd";bs);created=1700000000;keyid="edkey";alg="ed25519"
```

## 4. Signature-Input and Signature dictionaries

`signature-input` is a Structured-Field **dictionary** with **one or more**
members `label=(<components>)<params>`, separated by `, `:

- each `label` is a unique dictionary key;
- `<components>` is zero or more space-separated component identifiers (a quoted
  name with optional parameters, §2);
- `<params>` is zero or more `;name=value`, where `created` and `expires` are
  integers and `keyid`, `alg`, `nonce`, `tag` are quoted strings.

`keyid` is **required** for every member. The member value `(<components>)<params>`
is used verbatim as that member's `@signature-params` value (§3).

`signature` is a dictionary of `label=:<base64>:` members; the base64 decodes to
the raw signature bytes (64 for ed25519, 32 for hmac-sha256). **Every** label in
`signature-input` must have a matching `signature` member. A field that does not
parse under this grammar, a member missing `keyid`, or a label without a matching
signature makes the bundle unevaluatable (§8).

Each labelled member is one **candidate** signature.

## 5. Per-candidate policy

Evaluate each candidate independently with the following ordered checks; the
**first** that fires is that candidate's outcome. `<covered>` is the comma-joined
list of the candidate's serialised covered identifiers in declared order.

1. **unknown_key** — `keyid` is not in `keys`. → reason `unknown_key`, stage 1
2. **alg_mismatch** — a declared `alg` differs from the key's bound `alg`. Checked
   **before** any cryptography, so an asymmetric→symmetric downgrade can never be
   "verified" under the wrong primitive. → `alg_mismatch`, stage 2
3. **signature_invalid** — reconstruct the signature base (§3) and the signature
   does not verify under the key using the bound algorithm (ed25519 over the base,
   or HMAC-SHA256 of the base). → `signature_invalid`, stage 3
4. **coverage_inadequate** — the covered set (by component **name**, ignoring
   parameters) omits a required component. Required = `@method`, `@authority`,
   `@path` always, plus `content-digest` when the body is non-empty. →
   `coverage_inadequate`, stage 4
5. **expired** — `expires` is present and `now > expires`. → `expired`, stage 5
6. **not_yet_valid** — `created` is present and `now < created`. →
   `not_yet_valid`, stage 6
7. **digest_mismatch** — `content-digest` is covered and its plain field value is
   not `sha-256=:base64(sha256(body)):`. → `digest_mismatch`, stage 7
8. otherwise the candidate is **verified** (stage 8).

Notes: freshness boundaries are inclusive (`now == created` and `now == expires`
are valid); HMAC comparison must be constant-time.

## 6. Cross-candidate selection

A bundle is accepted iff **at least one** candidate is verified.

- **Accepted** → the selected signature is the verified candidate covering the
  **most** components; ties are broken by ascending label. The decision reports
  that candidate's label and covered list.
- **Rejected** → the reported candidate is the one that reached the **furthest**
  stage before failing (the highest stage number in §5); ties are broken by
  ascending label. The decision reports that candidate's reason and covered list
  (`-` for stages 1–3, the covered list for stages 4–7).

## 7. Decision line

Print exactly one line to stdout:

```
<verdict> <selector> <covered>
```

`<verdict>` is `verified` or `rejected`. `<selector>` is the **accepted
signature's label** when verified, or the **reason code** when rejected.
`<covered>` is the selected candidate's covered list, or `-` as defined in §6.

### Worked examples (several signatures)

A request carrying two verifying candidates of different coverage —

```
gateway=("@method" "@authority" "@path" "@query");... , edge=("@method" "@authority" "@path");...
```

— is accepted under the wider one: `verified gateway "@method","@authority","@path","@query"`.

A request whose candidate `aaa` fails at stage 1 (`unknown_key`) and candidate
`bbb` fails at stage 5 (`expired`) is rejected for the furthest failure:
`rejected expired "@method","@authority","@path","content-digest"` (bbb's covered
list).

## 8. Unevaluatable input

Input that cannot be evaluated must cause a **non-zero exit** with a message on
stderr — never a panic and never a decision line. This includes: input that is
not a JSON object; an empty or missing `keys`; a missing `signature-input` or
`signature` header; a `signature-input`/`signature` that does not parse under §4;
a member missing `keyid`; a label with no matching `signature` member; or a
covered component that is unresolvable under §2. A `rejected` verdict is a normal
result and exits zero.

## 9. Algorithms

ed25519 and HMAC-SHA256 only, both from the Go standard library
(`crypto/ed25519`, `crypto/hmac`, `crypto/sha256`). No external dependency is
required or permitted.

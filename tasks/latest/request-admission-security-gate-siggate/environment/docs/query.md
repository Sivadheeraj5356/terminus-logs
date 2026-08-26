# Canonical query and request

## Canonical request

UTF-8, exactly seven LF-joined lines, **no** trailing LF after the last line:

```text
METHOD
PATH
CANONICAL_QUERY
CANONICAL_HEADERS
CONTENT_DIGEST
CREATED_DECIMAL
EXPIRES_DECIMAL
```

- `METHOD` / `PATH` are the envelope strings **verbatim** (do not force-case
  the method; do not `Clean`/decode/normalize the path — `/./`, `/../`, `//`,
  trailing `/`, and percent octets stay literal). `path` must begin with `/`
  or the envelope is `envelope_invalid`.
- Query: see below.
- Headers: walk `covered` left-to-right; resolve names case-insensitively;
  emit covered name **lowercased**; trim OWS at value **edges only** per the
  `--profile` `ows_mask` (see `profile.md`). Sample profile `ows_mask = 3`
  trims ASCII `SP`/`HTAB` only — **not** NBSP, CR, LF, VT, FF, or other
  Unicode spaces. Interior CR/LF/HTAB/SP and Unicode spaces are always
  literal MAC material (never collapsed). Format `name:value` with no space
  after `:`; join with LF. Missing covered name → `missing_covered_header`.
  Duplicate covered names emit the line twice.
- Content-digest / timestamps: see `digest.md`, `profile.md`, and `time.md`.

Envelope JSON fields: `method`, `path`, `query` (array of `{name,value}`),
`headers` (string→string), `body`, `covered` (header names in MAC order),
`created`, `expires`, `kid`, `mac`. Unknown fields ignored. Missing required
fields → `envelope_invalid`. `created`/`expires` must be JSON integers; a
fractional literal (e.g. `1700000000.0`) is `envelope_invalid`. The envelope
file itself must be strict UTF-8 JSON with no leading byte-order mark; a
BOM-prefixed file is `envelope_invalid`. After the single top-level JSON value
there must be **no trailing content** (including an extra JSON value or any
non-whitespace junk after the closing `}`/`]`). Whitespace-only trailing bytes
are allowed; any other trailing bytes are `envelope_invalid`.

## Canonical query

Build the canonical query as follows:

1. Treat each `{name,value}` as an ordered pair.
2. Sort the pairs so that names are ascending (bytewise UTF-8). When two pairs
   share a name, sort those pairs by value ascending (bytewise UTF-8).
3. Render each pair as `name=value` with no extra escaping in v1 fixtures.
4. Join with `&`. Zero parameters → empty string (still a line in the CR).

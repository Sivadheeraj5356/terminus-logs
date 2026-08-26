# Vellum release contract

`/app/scripts/release` produces one qualification bundle. This document defines the
public contract every release must satisfy. It does not describe how the current
implementation is wired.

## Invocation

```
/app/scripts/release [--source-root <abs>] [--output <abs>]
```

`--source-root` defaults to `/app`, `--output` defaults to `/output/release`.
The source root must be resolved from the supplied path; nothing may be
hard-coded to `/app`. The release must run fully offline.

## Output tree

```
<output>/
  native/libvellum.so
  python/vellum-<version>-py3-none-linux_x86_64.whl
  node/vellum-node-<version>.tgz
  metadata/dependency-inventory.json
  metadata/provenance.json
  metadata/provenance.sig
  metadata/release-public.pem
  SHA256SUMS
```

`<version>` is the trimmed contents of `/app/VERSION`. `SHA256SUMS` lists
`<sha256>  <relative-path>` for every other file in the tree, sorted by path.

## Documents and the canonical digest

A document is JSON limited to objects, arrays, strings, integers, booleans and
null. The canonical digest is the lowercase hex SHA-256 of the canonical
serialization, where canonicalization is:

- object: drop members whose value is null; if a key repeats, the last member
  wins; order the remaining members by key code point; canonicalize each value;
- string scalar: remove leading and trailing space, tab, carriage return and
  line feed;
- serialize compactly with no insignificant whitespace, JSON-escaped strings,
  integers in decimal.

The detached-content digest is the canonical digest of the value stored under
the member `content`, or absent when there is no such member.

## Runtime identity

The native library, the Python package and the Node package each expose an
identity object with these fields:

- `version`: trimmed `/app/VERSION`;
- `revision`: trimmed `/app/REVISION`;
- `abi_fingerprint`: lowercase hex SHA-256 of the canonical ABI descriptor
  generated from `/app/interface/document.idl`;
- `dependency_closure_digest`: the `closure_digest` string from the dependency
  inventory (`sha256:<hex>`);
- `capabilities`: the sorted, de-duplicated capability names actually compiled
  into the native engine;
- `release_id`: lowercase hex SHA-256 of the UTF-8 bytes of

  ```
  vellum-release-v1\nversion=<version>\nrevision=<revision>\nabi=<abi_fingerprint>\ncapabilities=<caps>\nclosure=<dependency_closure_digest>\n
  ```

  where `<caps>` is the sorted capability names joined with `,` and `\n` is a
  single line feed.

All three surfaces must report identical values for every field, and each field
must equal the value independently derived from the immutable inputs.

## ABI descriptor

The canonical ABI descriptor is compact JSON:

```
{"capabilities":[<sorted names>],"operations":[{"name":..,"requires":..} sorted by name],"schema":1}
```

## Package APIs

- Native C ABI: `char *vellum_identity_json(void)`, `char
  *vellum_canonical_digest(const char *json)`, `char *vellum_detached_digest(const
  char *json)` (present only when the detached capability is compiled), and `void
  vellum_free(char *)`. Digest functions return lowercase hex or null on error.
- Python: `vellum.identity()` returns a dict with the identity fields;
  `vellum.canonical_digest(document)` accepts a dict/list/JSON string and returns
  the hex digest string.
- Node: `identity()` returns an object with the identity fields;
  `canonicalDigest(document)` returns the hex digest string.

Both packages install and run offline and stay self-contained after being
relocated away from `/app` and the release output directory.

## Dependency inventory

```
{
  "schema_version": 1,
  "components": [
    {"ecosystem": "cargo|native", "name": "..", "version": "..",
     "source": "vendored|workspace|toolchain", "checksum": "sha256:<hex>"}
  ],
  "closure_digest": "sha256:<hex>"
}
```

Components describe the closure actually compiled into the native library,
sorted by `(ecosystem, name, version, checksum)`. `closure_digest` is
`sha256:` plus the hex SHA-256 of the compact JSON of the `components` array.

## Provenance

```
{
  "release_id": "<hex>",
  "runtime": {"abi_fingerprint": "<hex>", "capabilities": [..],
              "dependency_closure_digest": "sha256:<hex>"},
  "schema_version": 1,
  "source": {"revision": "..", "version": ".."},
  "subjects": [{"path": "<relative>", "sha256": "sha256:<hex>", "size": <int>}]
}
```

Subjects are the final native library, wheel, Node tarball and dependency
inventory, sorted by path, measured after all other build steps complete.
`provenance.sig` is the raw Ed25519 signature over the exact bytes of
`provenance.json` produced with `/app/policy/qualification-ed25519.key`;
`release-public.pem` is the matching public key.

## Reproducibility

For identical source inputs, every file under the output tree must be
byte-identical across differences in: absolute source/output paths, `HOME` and
`TMPDIR`, source file mtimes, umask, and harmless developer-only feature
override variables. Archive ordering, modes, timestamps, owner/group and gzip
headers must be normalized, and native build-id and embedded build paths must be
absent or deterministic.

## Incremental releases

After a valid change to an immutable release input in a working copy (the IDL,
the release profile, `VERSION` or `REVISION`), an in-place release must equal a
clean release of the same modified source. Checked-in generated files under
`/app/generated/checked-in` must not be rewritten by a release.

## Immutable inputs

`/app/docs`, `/app/interface`, `/app/config`, `/app/VERSION`, `/app/REVISION`,
`/app/policy`, `/app/fixtures`, `/app/vendor`, `/app/generated/checked-in`, and
the checked-in Cargo/Python/Node lockfiles are release inputs and must not be
modified by the fix. A release may write only under its output directory,
`/app/target`, and `/app/.state`.

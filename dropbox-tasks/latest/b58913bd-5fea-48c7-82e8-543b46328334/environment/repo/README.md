# formula-catalog

A small utility the catalog tooling uses to keep a formula's published releases
in order. When the resolver needs to know which of two releases is newer, say
while planning an upgrade or pinning a dependency, it calls into
`internal/version`. The same package backs the release-history view through
`version.Sort` and `version.Newest`.

## Layout

- `cmd/formula-order`: the command-line entry point. It takes two version
  strings and prints their relative order.
- `internal/version`: the ordering logic (`version.Compare`, `version.Sort`,
  `version.Newest`).
- `examples.json`: a sample of reference orderings the catalog expects.

## Building and running

```
go build ./cmd/formula-order
./formula-order 1.2.3 1.2.4      # prints -1
```

`go test ./...` runs the unit tests.

## Notes

Ordering currently covers plain dotted-number releases. Catalogs also publish
decorated versions: pre-releases like `alpha`, `beta`, `pre`, and `rc`, patch
and post levels, single-letter revisions, and versions that differ only in
their separators or leading zeros. `examples.json` records how those rank.

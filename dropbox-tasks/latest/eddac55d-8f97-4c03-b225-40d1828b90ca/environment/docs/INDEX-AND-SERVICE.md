# Derived index and lookup service

`tzforge build` reads the corpus and writes the zone files, the manifest and the
index. `tzforge serve` answers lookups over the timeline. Both take `--config`,
defaulting to `/app/config/tzforge.toml`.

## Outputs

Zone files are written to `zoneinfo/<jurisdiction>` under the configured output
directory, one per jurisdiction.

`manifest.json` sits beside `zoneinfo/`. It is canonical JSON: object members sorted
by name, no insignificant whitespace, a single trailing newline. It carries `version`
and `zones`; `zones` is ordered by jurisdiction name, each member carrying `zone`,
`sha256` of that jurisdiction's zone file, `transition_count`, `first_transition` and
`last_transition`.

Building an unchanged corpus twice produces identical bytes and leaves the index
holding the same rows.

## Index

Migrations under `/app/migrations` define the schema and are applied in name order.

`zones` carries one row per jurisdiction: its meridian, the SHA-256 of its zone file,
its transition count, its first and last transition instants, and its POSIX footer.

`ordinances` carries every record of the jurisdiction's corpus, establishing and
repeal alike, with its kind, `enacted` date, enactment sequence, effective instant as
a Unix epoch, effective anchor, resolved standard offset, and its `basis` and
`repeals` references as published.

`transitions` carries one row per emitted transition: the instant, the offsets from UT
before and after it, the daylight saving flag and abbreviation after it, and the
ordinance that produced it.

`segments` carries one row per governing interval as a `tstzrange`, with the governing
ordinance and its standard offset. The last interval of a jurisdiction has no upper
bound. Two intervals of one jurisdiction may not overlap.

## Service

The service listens on the configured address.

`GET /v1/zones` lists the jurisdictions.

`GET /v1/at?zone=&epoch=` gives `utoff`, `isdst`, `abbrev` and the governing
`ordinance` at that Unix epoch, which may lie beyond the last transition.

`GET /v1/transitions?zone=&from=&to=&limit=&cursor=` pages the transitions of a
jurisdiction in ascending order. `from` and `to` bound the instant inclusively;
`limit` defaults to 100 and may not exceed 1000; `cursor` resumes strictly after the
instant given. The reply carries `items` and `next_cursor`, the latter null when the
page is the last.

`POST /v1/resolve` takes `zone`, `local` as `YYYY-MM-DDThh:mm:ss`, an optional
`policy` of `reject` or `shift` defaulting to `reject`, and an optional `fold` of 0 or
1 defaulting to 0. It replies with `epoch`, `kind` — one of `unique`, `fold`, `gap` —
and the offset, flag and abbreviation there. A civil time that exists nowhere under
the `reject` policy is answered `409`.

`GET /v1/tzif/{zone}` serves the zone file. Its `ETag` is the SHA-256 of the bytes,
in double quotes; a matching `If-None-Match` is answered `304`.

An unknown jurisdiction is answered `404`. A malformed or missing parameter is
answered `400`.

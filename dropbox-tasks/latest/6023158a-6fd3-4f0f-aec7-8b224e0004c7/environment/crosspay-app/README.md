# crosspay

A cross-border payroll calculator written in Go and backed by SQLite. It keeps
employees and their logged hours in a local database, computes gross pay, and
runs a progressive statutory withholding schedule to arrive at net pay. For
international runs it reads a country's primary currency and continent from a
bundled reference dataset and reports amounts in that currency's own minor unit.

## Build

    go build -o /app/crosspay .

Go is already installed and on the PATH; the build is standard-library only. The
`sqlite3` CLI is used for storage. The whole tool runs offline: the country
commands read the bundled reference dataset at `/app/reference/countries.json`.

## Money

All amounts are integer micro-units of a major currency: 1000000 micro-units is
one whole major unit. Rates are integer basis points. There is no floating point
anywhere in the system.

## Where to look

- `docs/spec.md` is the authoritative contract: command surface, output tokens,
  the statutory schedule constants and the pinned country codes.
- `schedules.go` holds the statutory withholding tables; `contrib.go` holds the
  employer social-contribution rules and country floors; `fx.go` holds the pivot
  cross-rate table.
- `country.go` holds the country-metadata loader for the bundled dataset.
- `scripts/` has small demo and maintenance helpers.

Beyond net pay the tool also computes an employer social contribution
(`social`), converts amounts to a base currency through a pivot (`convert`), and
aggregates assigned countries into a ranked cost report (`assign`, `report`).

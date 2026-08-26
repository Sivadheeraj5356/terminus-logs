// Command crosspay is a cross-border payroll calculator backed by SQLite. It
// stores employees and the hours they work, computes gross pay in micro-units of
// a major currency, and applies a progressive statutory withholding schedule to
// produce net pay.
//
// The cross-border piece reads country metadata (primary currency and
// continent) from a bundled reference dataset, selects the statutory schedule
// that applies to the country's region, and reports the pay amounts rounded to
// that currency's own minor unit.
//
// The binary is built with `go build -o /app/crosspay .` using only the Go
// standard library and the sqlite3 CLI for storage; the tool runs fully offline
// and reads the dataset at /app/reference/countries.json. The full command
// surface, output tokens, schedule constants and pinned country codes are
// documented in /app/docs/spec.md.
package main

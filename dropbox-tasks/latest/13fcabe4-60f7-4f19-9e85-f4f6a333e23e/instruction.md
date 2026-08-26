# Repair the offline DNSSEC publisher

The offline publisher in `/app` produces inconsistent releases after interrupted DNSKEY rollovers and legacy snapshot imports.

Repair the Go implementation shipped from environment sources into `/app`. Static or hand-written output is not sufficient; `/output/example.test.signed` and `/output/publication-manifest.json` must be produced by the normal publish pipeline through `/app/bin/zonepub`.

For the supplied workflows, publishing must produce:

- `/output/example.test.signed`
- `/output/publication-manifest.json`

The resulting signed zone must validate against the bundled trust anchor (`dnssec_valid`) and must preserve valid positive answers, wildcard answers, delegations, and authenticated negative answers for empty non-terminal names.

The release index at `/output/publication-manifest.json` uses `schema_version` 2 and records the effective SOA counter in the `serial` field for the signed zone origin. Manifest key lineage fields are documented in `/app/README.md`.

The repaired publisher must also satisfy all of the following:

- an interrupted release can be resumed safely after a process restart;
- unchanged inputs published with the same fixed evaluation epoch are byte-identical and do not add duplicate release history;
- retired or revoked DNSKEY material is never reactivated by an imported snapshot;
- the effective SOA counter never moves backward, including across 32-bit wraparound;
- supported legacy snapshots remain importable and inspectable;
- unsupported or invalid snapshots fail without changing the last good release;
- the existing CLI, exit-code behavior, output schema, output naming, and successful normal-rollover behavior remain compatible;
- the publisher continues to work for arbitrary supported zone origins and DNSKEY inventories, not only the supplied names and key tags;
- input fixtures under `/data` must not be modified during verifier runs.

The container image installs Go at `/usr/local/go` and prepends `/usr/local/go/bin` to PATH.

Build the application with:

```bash
make -C /app build
```

Reset the visible writable workflows with:

```bash
/app/scripts/reset-workflows.sh
```

Reproduce the supplied cases with:

```bash
/app/scripts/repro.sh normal
/app/scripts/repro.sh interrupted
/app/scripts/repro.sh rollback
/app/scripts/repro.sh wrap
```

The workflows use only local files and bundled dnssec-signzone utilities. Do not add network dependencies.

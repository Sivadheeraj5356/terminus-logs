# Zone Publisher CLI Contract

`zone-publisher` is the offline gate used by DNS operations before pending
authoritative-zone changes are pushed to primary name servers. It reviews a zone
snapshot against a proposed change journal, publication-freeze windows, and scoped
exceptions, then writes one canonical JSON publication report.

`zone-publisher` requires `--zone`, `--journal`, `--freezes`, `--exceptions`, and
`--report`; missing, duplicate, or unknown flags are fatal contract errors. Flag
values must be filesystem paths. The tool does not accept configuration files or
environment-driven input aliases.

A valid input set with no blocking findings exits 0 and writes the report.
A valid input set with one or more blocking findings exits 1 and writes the report.
Fatal contract or input errors exit 2.

Stdout is empty for every outcome. Stderr is reserved for fatal errors and should
contain a concise human-readable reason. Progress banners, timing summaries, and
debug dumps must not appear on either stream for successful or blocked runs.

Report replacement is atomic for exit 0 and exit 1. Implementations should write
through a temporary sibling and replace the destination only after the full report
body is ready. On exit 2, no new report is created; if a report already exists at
the target path, it remains byte-for-byte unchanged.

The program must not read network resources or helper binaries. All policy knowledge
comes from the four input files and the repository documentation under `/app/docs/`.

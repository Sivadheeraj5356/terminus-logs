# Usage

Run the adjudicator directly with `node bin/windowjudge.js`. The program reads
one JSON document from stdin and writes one JSON object to stdout, then exits.

The normative behavior specification lives in `docs/ceremony-windows.md`. Recorded input
streams are under `testdata/`; replay one with `scripts/replay.sh
testdata/stream-01.json`. The streams are sample inputs only and carry no
expected outputs.

`make check` runs `node --check` over the entry point and the engine module.

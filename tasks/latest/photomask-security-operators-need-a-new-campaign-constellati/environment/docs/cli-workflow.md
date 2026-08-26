# Command workflow

All input paths must be absolute. `threatcomp adjudicate --observations PATH --policy PATH` reads newline-delimited observation objects and one policy object. If `THREATCOMP_FIXTURE_DIR` is an absolute directory and contains `observations.jsonl`, those lines are appended. Adjudication atomically writes `/app/state/evidence-board.json`.

`threatcomp compose` reads only `/app/state/evidence-board.json` and writes `/app/state/campaign-constellation.json`. It also appends one canonical JSON line to `/app/state/constellation-chronicle.jsonl` only when the constellation payload digest changes. Epoch starts at 1 and increases by one on changed input. Identical replay leaves both files byte-identical.

`threatcomp brief` reads only `/app/state/campaign-constellation.json`, validates its checksum and board lineage, and writes `/app/output/campaign-brief.json`. Missing or malformed input exits 2 with `ERROR INPUT`. Contract or checksum failure exits 1 with `ERROR VALIDATION`.

# Legacy Record Decoder

The decoder at `/app/environment` reads paired binary dumps and text exports, compares them for compatibility, and writes a validated bundle to `/app/output/legacy_record_bundle.json`. The pipeline is currently broken: decoded pairs are misreported as compatible when they diverge, malformed binary records pass silently instead of being flagged, and field extraction from the binary format is incorrect.

Fix the source under `/app/environment/src` and `/app/environment/tools` so the normal build-and-run sequence regenerates a correct bundle. The decoy modules ending in `_stub.rs` are alternate paths not on the active decoder. Run `/app/environment/scripts/build_all.sh`, then execute the xscope checker documented in `/app/environment/docs/notes.md`. If local state becomes dirty, run `/app/environment/scripts/clear_scratch.sh` before retrying.

## Requirements

The output bundle at `/app/output/legacy_record_bundle.json` must be a valid JSON object that the verifier can parse and validate. The bundle must contain output from processing both fixture groups (set_a and set_b), and it must correctly report which record pairs are compatible across binary and text representations.

Records from the binary dumps must be decoded so that their field values match the authoritative values from the text exports exactly. Pairs are only compatible when all fields agree; partial agreement is not sufficient.

Records with structural problems must be identified and reported separately from compatible pairs. Malformed inputs must not be silently normalized or marked as compatible.

The bundle must be generated fresh by the build pipeline each time—hand-written outputs or static fixtures are not acceptable. The verifier will check that the output matches expected structure and content.

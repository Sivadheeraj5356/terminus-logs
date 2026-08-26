# Policy contract (ghost densify emit)

Speedrun practice densify emits a ghost seal under the published driver.
Numeric and digest policy lives here. Rebuild through `/app/driver/emit_ghost.sh`.

## Paths

Annex fixtures sit at `/app/data/annex_slice36`.
Band profiles sit at `/app/data/bands/profiles`.
Closed algebra skeleton sits at `/app/fixtures/closed_algebra.json`.
Ghost seal output sits at `/app/output/ghost_seal.json`.

## Emit path

`/app/driver/emit_ghost.sh` rebuilds cores and writes the ghost seal in one pass.
`/app/driver/compile_cores.sh` (also `/app/environment/driver/compile_cores.sh`) builds three Java tools under `/app/work` with javac and jar.
`/app/work/sep_tool` comes from `/app/q7` (also `/app/environment/q7`).
`/app/work/fold_tool` comes from `/app/m4` (also `/app/environment/m4`).
`/app/work/tie_tool` comes from `/app/v9` (also `/app/environment/v9`).
emit_ghost.sh must invoke those tools so sep_tool writes `/app/work/cut.json`, fold_tool writes `/app/work/pack.json`, and tie_tool writes `/app/output/ghost_seal.json`.
Checks may rerun `bash /app/environment/driver/compile_cores.sh` then invoke those binaries in order.
First call `/app/work/sep_tool /app/data/annex_slice36 /app/data/bands/profiles /app/work/cut.json`.
Next call `/app/work/fold_tool /app/data/annex_slice36 /app/data/bands/profiles /app/work/pack.json` with CUT_CTX pointing at `/app/work/cut.json`.
Finally call `/app/work/tie_tool /app/data/annex_slice36 /app/work /app/output/ghost_seal.json`.
fold_tool reads cut context from the CUT_CTX environment variable path.
Library sources under `/app` must themselves be correct; a driver rewritten to skip those tools does not satisfy this contract.

Ingest annex frames first into cut material using key-stable lane order.
Densify under tick budgets with that cut context available.
Bind independent query-context replay into the final ghost seal.
Local score witnesses can look calm while independent replay on stress fixtures still fails obligation 486.
Static JSON hand-writes of the ghost seal do not satisfy this contract. Consecutive emits with unchanged sources must keep matching digests.
When fixtures arrive in different ingest orders, observable fields must stay equivalent (same digests and pack totals modulo published observation windows).

## Output schema (ghost_seal.json)

Top-level object members follow.

schema_version is a string member that must be the literal text 1.0
band_rows is an array of per-band objects with profile_id, band_xfer_hex, kernel_span_hex, and e_admit
pack_rows is an array of per-frame objects with instance_id, lane_id, lane_hex, and floor_ratio
echo_hex is a 16-char lowercase hex member assembled under Densify packing
replay_root is a 16-char lowercase hex member assembled under Independent replay
algebra_violations is an integer count of failed closed-algebra checks under Obligation 486
local_witness_ok is a boolean observation that may be true even when algebra still fails
strategy_scan_hold is an integer count of adversarial reweights that still close obligation 486

band_rows members

profile_id is the band profile identifier string
band_xfer_hex is a 16-char lowercase hex digest assembled under Digests
kernel_span_hex is a 16-char lowercase hex digest assembled under Digests
e_admit is a JSON number that reports conserved band energy for that band. Emitted e_admit must equal that band's E within T0.

pack_rows members

instance_id is the annex instance identifier string
lane_id is the frame lane identifier string within that instance
lane_hex is a 16-char lowercase hex digest assembled under Densify packing
floor_ratio is a JSON number that reports density_hint divided by densify_floor

## Numeric precision class T0

T0 is 1.0e-9. energy_imbalance for a profile is the absolute gap between the sum of e_admit over bands and the sum of band energies E over bands. That gap must stay inside T0.

Observation window W0 is 16 chars for every hex digest field.

## Annex instance fixtures

Each JSON body under `/app/data/annex_slice36/instances` reports

id is the instance identifier string
client_pin is the client pin string
frames is an array of frame objects. Each object reports lane_id, tick_cost, density_hint, and pin_hex

## Digests

sha16(s) denotes the first 16 lowercase hex chars of sha256 over UTF-8 bytes of s.
A matching Python helper lives at `/app/common/digest.py` (`sha16`).
Use ASCII 0x3A as the field separator inside band digests and 0x7C as the lane join separator.

For each band profile under `/app/data/bands/profiles`

1. Build densify packing context first from all annex instances (see Densify packing).
2. packed_context_hex is sha16 of every lane_hex joined by 0x7C in lexicographic (instance_id, lane_id) order.
3. For each band in profile order, band_xfer_hex is sha16 of profile_id, band_name, e_admit formatted to 12 decimal places, and packed_context_hex joined by 0x3A.
4. kernel_span_hex is sha16 of profile_id, band_name, sorted lane_id values from cut material for instances that contribute tick cost under that profile, joined with 0x2C, and packed_context_hex joined by 0x3A.

Memo keys for ingest cut material must include the active lane_id and client_pin, not an arrival index.

## Key-stable ingest (cut material)

For each annex instance, process frames sorted by lane_id ascending (not arrival order).
For each frame, span_hex is sha16 of lane_id, client_pin, pin_hex, and tick_cost formatted to 6 decimal places, with those four fields separated by 0x7C.
Cut material lists (instance_id, lane_id, span_hex, tick_cost, density_hint) sorted by (instance_id, lane_id).

Arrival-order processing flips observales under ingest reorder.

## Densify packing

fold_tool reads cut material from CUT_CTX. Densify packing must use cut span_hex values; packing from raw annex frames alone is not sufficient.

For each cut row, apply the active densify_floor taken as the lowest densify_floor across profiles.

lane_hex is sha16 of instance_id, lane_id, density_hint formatted to 6 decimal places, and span_hex, with those four fields separated by 0x7C.
floor_ratio reports density_hint divided by densify_floor (lowest densify_floor across all profiles).
Densify floor requires floor_ratio + T0 to be at least 1.0 for every pack row.

echo_hex is sha16 of all lane_hex values joined by 0x7C in lexicographic (instance_id, lane_id) order.
packed_context_hex equals echo_hex under this contract.

Sum of tick_cost across cut rows for an instance must stay at or under that instance's contributing profile tick_cap when measured against the maximum tick_cap across profiles (resource limit). Violations count against obligation 486.

## Independent replay

replay_root is sha16 of annex_bytes_concat, packed_context_hex, and band_xfer_hex values joined by 0x7C in profile then band order, with 0x3A between those three parts.

annex_bytes_concat is the concatenation of raw file bytes for each instance path listed in `/app/data/annex_slice36/manifest.tsv`, in manifest row order.

Local witness construction may report local_witness_ok true using only local densify residuals. That does not discharge obligation 486. Independent replay must still run and populate replay_root from annex bytes plus packed and band material. Short-circuiting on a green local witness leaves algebra_violations nonzero when stress fixtures and strategy-proof reweights are applied.

## Obligation 486 / closed fixture algebra

algebra_violations is the integer total of these failed closed-algebra checks.
Count each pack row whose floor_ratio + T0 is below 1.0.
Count each profile whose energy_imbalance exceeds T0.
Count each strategy_scan_reweight w from `/app/fixtures/closed_algebra.json` for which any pack row has floor_ratio / w + T0 below 1.0.

strategy_scan_hold counts strategy_scan_reweights that still keep every pack row above the floor under that reweight.
Obligation 486 requires algebra_violations to be zero on the closed fixture algebra.

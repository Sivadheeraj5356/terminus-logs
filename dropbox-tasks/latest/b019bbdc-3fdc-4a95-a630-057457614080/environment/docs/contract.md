# Optical WDM / Raman pump numeric contract

Scientific-computing policy for undersea wavelength-division multiplex channel assignment and Raman cool-residual budgets.

## Topology

Scenarios under `/app/data/scenarios/<id>.json` define nodes (`regen` true/false), undirected spans with `cap_gbps`, `pump_mw`, and ordered `lambdas`, plus `cuts` (unavailable span ids), `demands`, `cool_factor`, and `mw_per_channel`.

## Demand ranking

Admit demands in ascending `priority`, breaking ties by ascending `id`.

## Admission phases

Each `run` executes plan → pump audit → commit. Provisional channel picks live in a draft lane until audit passes; failed attempts must release draft occupancy before the next demand is planned. Pump audit counts channels staged for the demand under test plus any already committed on that span.

Span capacity audit runs before channel staging for each demand, in ranked admission order. It must evaluate **every** span on the routed path, not only the first hop. For each hop span, compare `committed_gbps[span] + demand.gbps` against that span's `cap_gbps`, where `committed_gbps` includes gbps from demands already admitted earlier in the same run. Reject the demand when any hop would exceed its span cap after that addition.

## Routing

On the residual graph (cuts removed), each demand takes a shortest hop path. When multiple shortest paths exist, choose the lexicographically smallest `span_id` sequence joined by `>`.

## Wavelength continuity

For hop `i` originating at node `N` with previous channel `prev` (`prev = -1` on the first hop):

- First hop: assign the minimum free channel on the span from the span's `lambdas` list.
- If `N.regen` is true: assign the minimum free channel on the span (remux allowed).
- Else: the previous channel must remain free on the span and is reused; otherwise the demand is rejected. Do not substitute a different free channel when reuse fails.

Channels are occupied only after a demand is fully accepted. Provisional hop assignment during routing must not consume channels on a span before that demand passes capacity and pump admission.

## Pump draw

For each span after a tentative channel set of size `C`:

```
used_mw = cool[span] + C * mw_per_channel
```

Accept only when `used_mw <= pump_mw` (tolerance `1e-9`). After a successful scenario commit, persist:

```
cool[span] = cool_factor * used_mw
```

for every span that carries at least one channel in that commit. Spans with no channels in the latest commit keep their prior cool unchanged (including when a later scenario uses a disjoint span set). Initial cool values are `0` after `splicectl reset`.

## Settlement

For each unordered peer pair `(peer_a, peer_b)` appearing on any demand (store pair with `peer_a <= peer_b` lexicographically):

- `eligible_gbps` sums `gbps` of all demands on that pair
- `served_gbps` sums `gbps` of admitted demands on that pair
- `share = served_gbps / eligible_gbps` (0 when eligible is 0), formatted to four decimal places in the TSV

`settle_score` is the arithmetic mean of those shares (0 when no pairs).

## Digests

`digest_hex` is lowercase hex SHA-256 over digest lines sorted lexicographically, joined by `\n`, with a trailing newline. One line per served demand:

```
D|<demand_id>|path=<span_1>><span_2>|lam=<l1>,<l2>|gbps=<n>
```

Join hop `span_id` values in order with `>` (same separator as routing tie-break). Join hop `lambda` values in order with `,`. Longer paths extend naturally (e.g. `a>b>c` and `1,2,3`).

## Generation and journal

`splicectl reset` clears `/app/var/splicekit/pump_ledger.json` cool map and truncates `/app/var/splicekit/journal.jsonl`. Each successful `run` appends one journal line and sets `generation` to the journal line count after append (first successful run after reset yields `1`).

Before appending the new journal line, read the prior commit digest from the **last** non-empty line already in the journal (empty string when the journal is empty). Store that value as `prior_digest_hex` on the report and in `splicectl status` for the current session bundle.

Each journal line is exactly:

```
<generation>|<scenario_id>|<digest_hex>
```

with no extra fields or whitespace. `splicectl publish` writes `/app/output/*` from the last successful `run` bundle; `publish` without a prior successful `run` in the current session exits non-zero.

## Artifacts

- `/app/output/replan_report.json`: `scenario_id`, `served`, `rejected`, `total_gbps`, `pump_peak_mw`, `settle_score`, `feasible`, `generation`, `prior_digest_hex`, `digest_hex`
- `/app/output/lambda_trace.csv` header `demand_id,hop,span_id,lambda,gbps`
- `/app/output/settle_score.tsv` header `peer_a,peer_b,served_gbps,eligible_gbps,share`
- `/app/var/splicekit/pump_ledger.json`: `{"cool": {span_id: float, ...}}`
- `/app/var/splicekit/journal.jsonl`: one line per successful commit as above
- `splicectl status` JSON: `scenario_id`, `feasible`, `total_gbps`, `settle_score`, `generation`, `prior_digest_hex`, `digest_hex` matching the last successful `run` before `publish`

`feasible` is true only when `rejected` is empty.

## Negative paths

- Unknown scenario id: exit non-zero; write no output artifacts under `/app/output/`. Any id with no matching fixture under `/app/data/scenarios/` is unknown (for example `eq_missing_fixture`).
- Scenario with empty `demands`: exit non-zero; write no output artifacts.
- `publish` without a prior successful `run` after the latest `reset`: exit non-zero.

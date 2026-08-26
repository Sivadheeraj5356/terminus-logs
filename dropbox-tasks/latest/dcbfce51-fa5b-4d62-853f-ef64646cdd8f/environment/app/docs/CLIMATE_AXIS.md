# Climate model CF multi-member calendar axis

Climate simulation members that share a CF calendar can be combined onto one calendar-qualified CCF axis, with a monthly climatological reduction and a provenance report:

```bash
climconvert compact --manifest /app/data/climate-axis-manifest.toml
```

Working state under the configured `state_dir` records the last committed generation so previously incorporated members may be retired while their calendar instants remain on the axis. Authoritative calendar arithmetic is in `/app/docs/time-contract.md`.

## Manifest

A manifest (`schema_version = 1`) lists:

- Shared `calendar` and archive `units`
- Ordered `[[sources]]` entries with `path`, `role` (`committed` or `segment`), and optional `digest`
- Paths for `state_dir`, `archive_path`, `rollup_path`, `report_path`, and `cache_dir`
- A stable `run_id`

## Behavioral guarantees

1. A restarted run must produce the same logical archive and monthly climatological reduction as an uninterrupted run on the same inputs and working state.
2. Observations from a committed prefix remain available after their source shards are retired.
3. Member times may use different `units` origins but must share the same calendar (including `360_day` and `noleap`).
4. Identical overlap records (same canonical calendar instant, bounds, and variable payloads) appear once.
5. Records at the same canonical instant with different bounds or variable payloads are conflicts: the command fails with a non-zero exit and does not replace the last committed archive, rollup, report, or checkpoint.
6. Time centers, bounds, and every variable row stay aligned under the declared calendar arithmetic.
7. CCF and CFT members with equivalent content produce equivalent archives.
8. A cache hit for the monthly reduction matches a clean no-cache computation byte-for-byte.
9. Re-running a successful run leaves numerically identical archive, rollup, report, and generation identity.
10. The report describes the actually committed archive, rollup digests, and source lineage (including retired sources).
11. Existing `convert`, `append`, `resample`, `validate`, and `trace` behavior remains valid.
12. Source members and the last committed generation are not edited in place.

## Report

`/output/climate-axis-report.json` uses `report_format_version` **1** and includes:

- `committed_generation_id`
- `archive_path` / `archive_digest`
- `rollup_path` / `rollup_digest`
- `observation_count`
- `first_instant` / `last_instant` as `[year, month, day]`
- `recovery_outcome`
- `conflict`
- `source_lineage` entries with `path`, `digest`, `retired`, `observation_count`

Volatile wall-clock timestamps are not part of the published report.

## Scratch names

Temporary calendar drills may use scratch filenames such as `conflict.ccf`,
`extra_segment.ccf`, `merged.ccf`, `m1.ccf`, `m2.ccf`, `m.toml`, `mid.cft`,
`out.ccf`, `report.json`, and a `segs/` directory under a temporary workspace.
These names are not part of the durable production layout.

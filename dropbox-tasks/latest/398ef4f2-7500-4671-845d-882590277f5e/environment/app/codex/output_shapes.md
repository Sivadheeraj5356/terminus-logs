output shapes

input and output roots are configurable at runtime through two environment variables. AIRBRIDGE_DATA points at the input root that holds the ramplog and feebook subfolders and defaults to /app when unset. AIRBRIDGE_OUT points at the directory where cycles.ndjson, summary.toml, and digest.txt are written and defaults to /app/output when unset. both variables must be honoured so that the same binary can be pointed at alternative fixtures without recompilation.

three files are emitted under the output root on every run. all three must be regenerated from scratch, including the case where a prior run left stale files in the directory.

cycles.ndjson contains one json object per line with exactly nine keys in this order: cycle_id, carrier_iata, gate_zone, body_code, mtow_tons, dwell_minutes, net_fee_cents, verdict, tier_version. integers are emitted as json integers without quotes. the file is sorted ascending by cycle_id and then by gate_zone for ties. each line ends in a single newline byte. there is no trailing blank line.

summary.toml opens with the literal line schema = "airbridge_summary_v1" followed by an array of tables named totals. each totals entry has keys carrier_iata, verdict, cycle_count, and billed_cents in that order. the array is sorted ascending by carrier_iata, then by verdict. cycle_count counts every cycle that produced that verdict for that carrier. billed_cents sums the net_fee_cents column for the same set.

digest.txt contains exactly one line of sixty four lowercase hex characters followed by a newline. the digest is sha256 over the concatenation of canonical pipe form lines, one per cycle, in the same sort order used in cycles.ndjson. each canonical line joins cycle_id, carrier_iata, gate_zone, body_code, mtow_tons, dwell_minutes, net_fee_cents, verdict, tier_version by the pipe character and is terminated by a newline. there is no trailing pipe and no trailing blank line.

tier_version on a record is the effective_from string of the airframe_rates row that priced it. STALE_TIER records are the one non billable exception: they still carry tier_version equal to the effective_from of the row active at gate_assigned_ts, so the field records the tier that was attempted at the moment the gate was assigned. REJECTED_NUMERIC, REJECTED_TIER, and VOID_DUPLICATE carry an empty tier_version because no tier was resolved for them.

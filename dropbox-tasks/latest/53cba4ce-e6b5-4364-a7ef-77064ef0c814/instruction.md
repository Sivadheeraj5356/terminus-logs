The Station Systems Freeze has fixed our observatory's decision record, and the spectral analysis host is due for its audit. The Java estimator under /app/service produces the station's FFT band-power spectra for the geomagnetic channels; its working tree, however, no longer reflects the record: the build manifest resolves against artifact versions whose approvals are not in force, request values reach the telemetry store as concatenated statement text contrary to station policy, and the estimator computes to a spectral methods revision that no longer governs.

Restore the host to the decision record as of the freeze:

- `mvn -o -DskipTests package` run in /app/service must succeed against the station Maven repository (analysis hosts resolve offline) and produce /app/service/target/spectra-svc.jar, linking only dependency versions whose approval is in force.
- With the jar running, the requests described in /app/requests/samples.http must return correct band-power spectra for every enrolled channel under the in-force revision of SMP-7, preserving the documented response shape.
- Values derived from requests must reach the telemetry store only through bound parameters.
- File the provenance dossier required by SOP-9 §6 at /app/audit/provenance_dossier.json, following /app/archive/dossier_schema.md exactly — its object and key names letter for letter. Some of its fields describe the working tree as shipped, so capture those facts before you change anything.

The station archive under /app/archive, the review registry, and the telemetry holdings in the local `meridian` PostgreSQL cluster are the record you audit against: treat them as read-only. Nothing on the host restates the in-force decisions; reconcile them from the record yourself.

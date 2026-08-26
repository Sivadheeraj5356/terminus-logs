# StreamVault 2025 Security Hardening Runbook

This runbook contains approved controls, exception authority, and retained historical
discussion. Only headings marked `Control` or `Rationale` are authoritative. Proposals,
drafts, rollback notes, and historical records are context and must not be treated as
approvals.

## Approved controls

### Control: SV-IDENTITY-01

The administrative identity comes from the fleet registry for the selected site. Factory
usernames must not be retained, even when an export appears to use a site-specific value.

### Control: SV-CREDENTIAL-02

Static administrative passwords are prohibited. Deployments reference the runtime
variable `STREAMVAULT_ADMIN_PASSWORD` by name. Neither the source value nor a reversible
representation may appear in patched configuration, reports, warnings, or logs.

### Control: SV-AUTH-03

Anonymous access is disabled in every deployment profile. There is no site-level exception
mechanism for this control.

### Control: SV-TLS-04

Transport authentication is mandatory, including for loopback-only administrative and
metrics services. Isolated networks are not an alternative to TLS.

### Control: SV-BIND-05

The primary NVR listener uses the registry-approved address. Operators must not infer a
bind address from an archived Compose export, camera subnet, or media fixture.

### Control: SV-INGEST-06

Only enabled cameras with a regular local media fixture contribute an ingest port. Ports
are normalized numerically, deduplicated, and exposed on loopback using TCP. Disabled
cameras, missing fixtures, path-traversing fixture names, and ports outside the approved
range are not deployable evidence.

### Control: SV-SERVICE-07

Service bindings default to loopback. A current, site-scoped exception may override only
the binding of a service named in both the exception value and the input service manifest.
An exception without an exact rationale heading in this runbook has no authority. A
non-loopback exception is also constrained to the service networks approved for the site's
profile; exception prose cannot authorize an address outside those registry CIDRs.

### Control: SV-RETENTION-08

Recording retention is bounded by the fleet policy for the site's registered profile.
Operators clamp exports to that interval; they do not infer a policy from available disk
space. A current, rationale-authorized exception may name one explicit duration from one
through 365 days.

## Approved exception rationales

### Rationale: EXC-PLANT7-INGEST

Plant 7's isolated camera VLAN reaches the ingest process at `10.70.0.15` during the
approved transition period. This exception is scoped to `camera-ingest`. It does not
authorize the administration interface, metrics interface, unknown sidecars, credential
changes, anonymous access, or TLS changes.

### Rationale: EXC-PLANT7-RETENTION

Plant 7 retains 45 days during the incident-investigation transition. This approval is
limited to recording retention and does not alter camera eligibility or service exposure.

### Rationale: EXC-PLANT7-RETENTION-EXTENDED

This approved decision extends the Plant 7 incident-retention period to 60 days when it
supersedes the earlier transition decision in the fleet registry.

### Rationale: EXC-PLANT7-RETENTION-LEGAL

This approved legal-hold decision retains 75 days when the fleet registry makes it the
unique successor of every other current retention decision.

### Rationale: EXC-PLANT7-RETENTION-FINAL

This approved closure decision retains 50 days when it is the unique terminal decision in
the registered supersession graph.

## Retained change-control history

### Draft identity proposal

An early 2024 proposal suggested preserving the `admin` account to reduce cutover work.
Identity governance rejected it because a shared factory account prevents site-level
attribution. The proposal never became an approved control.

### Port rollback rehearsal

A rollback exercise temporarily used port 8554 for every test camera. The exercise was
limited to the lab and did not establish a production port. Fleet registry rows remain
the authority for enabled cameras and approved ingest ports.

### Metrics binding discussion

An operator chat suggested placing metrics on the camera VLAN while the Plant 7 exception
was active. Security review rejected that interpretation: the rationale names only the
ingest service. Exceptions do not extend to similarly located or operationally related
services.

### Expired exception handling

Expired records are retained in the database for audit history. They must produce a
warning and must not affect the patched configuration. A later database timestamp cannot
make an exception authoritative when its rationale heading is absent.

### Media fixture validation

Archived exports have included absolute paths, parent-directory references, broken
symlinks, and stale camera rows. Only a regular file named directly under the export's
media directory is deployment evidence. The report records accepted fixture filenames,
not host paths.

### Deterministic evidence

Filesystem enumeration and SQLite row order vary across recovery hosts. Configuration
arrays, report changes, warnings, and evidence therefore use their documented canonical
order. Repeated remediation of identical inputs must be byte-identical.

## Final authority statement

The approved control headings and exact exception rationale headings above govern the
deployment. Historical prose explains rejected alternatives and does not supersede them.

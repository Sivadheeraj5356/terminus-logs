# StreamVault Remediation Output Contract

This contract defines the deployment artifacts consumed by the offline compliance
importer.

The policy date is the fixed literal `2025-12-31`. It is a reproducibility boundary, not
the current date; do not read the system clock when evaluating exception expiry or writing
`policy_date`.

## Recovery tooling

The isolated recovery host provides `sqlite3`, `jq`, `yq`, and `sha256sum` as its approved
administrative tools. Query the fleet registry through `sqlite3`, normalize JSON through
`jq`, read and emit YAML through `yq`, and hash the published artifacts through
`sha256sum`; the compliance audit records actual invocation of all four commands.

## Canonical files

Create exactly `streamvault.yaml`, `services.json`, `hardening-report.json`, and
`bundle-manifest.json` under the requested output directory. JSON uses two-space indentation, recursively sorted object
keys, and one trailing newline. Emit YAML through `yq` from normalized JSON, without a
document separator and with one trailing newline.

Camera ports are numerically ascending. Report changes are sorted by `control_id`, then
`path`; evidence arrays are sorted by canonical JSON. Repeated remediation of identical
inputs must be byte-identical regardless of filesystem or SQLite row order.

An enabled camera's approved port is valid only in the inclusive range `1024..65535`.
Any eligible camera row outside that range makes the registry unsafe and the recovery
must fail; port 80, for example, is invalid rather than ignored.

Write each `camera-ingest` port mapping in the exact form
`127.0.0.1:<port>:<port>/tcp`; for example, port 11554 becomes
`127.0.0.1:11554:11554/tcp`.

## Evidence report

The report has this shape:

```json
{
  "policy_date": "2025-12-31",
  "site_id": "plant-7",
  "changes": [
    {
      "control_id": "SV-IDENTITY-01",
      "path": "security.admin_user",
      "before": "admin",
      "after": "sv-plant7-admin",
      "evidence": [
        {"source": "sqlite:sites", "key": "site_id", "value": "plant-7"},
        {"source": "runbook", "rationale_id": "SV-IDENTITY-01"}
      ]
    }
  ],
  "warnings": []
}
```

Record every controlled output path even when already compliant. Use `null` for an absent
before-value. Report a present `security.admin_password` only as `[REDACTED]`, then remove
it; never emit the original secret. The secured YAML must set the exact field
`security.admin_password_env` to `STREAMVAULT_ADMIN_PASSWORD`. `SV-INGEST-06` has separate changes for
`network.ingest_ports` and `services.camera-ingest.ports`.

`SV-SERVICE-07` records one change for every input service's bind field. Use the exact path
`services.<service_name>.bind`; for example, the ingest entry is
`services.camera-ingest.bind`. Do not replace these entries with one aggregate `services`
change.

Each change includes its runbook and relevant SQLite evidence. Ingest evidence identifies
accepted camera rows and media filenames. Retention evidence identifies the profile in
`sqlite:retention_policies`. Applied exceptions add `sqlite:exceptions` evidence and their
rationale heading.

Resolve exception authority before applying an approved value. Two or more unexpired rows
for the selected site and control cannot be resolved by choosing the first or last SQL row,
even when their values are equal. Resolve them only through the supersession graph below;
if that graph does not establish one effective decision, report the state as ambiguous and
preserve any previously published bundle.

A retention-policy row is valid only when `min_days` and `max_days` are integers in
`1..365` and `min_days <= max_days`. Inverted bounds such as `min_days=90` and
`max_days=10` are a fatal registry error; do not clamp against them or publish output.

## Exception supersession graphs

The registry table
`exception_supersessions(site_id, control_id, predecessor_rationale_id, successor_rationale_id)`
orders competing current authorized exceptions. First filter exceptions by selected site,
accepted control, policy date, and exact runbook rationale. Then build a directed graph for
each control from edges whose two endpoints are both in that filtered candidate set. An
edge `A -> B` means decision B supersedes decision A. Edges involving an inactive,
expired, unauthorized, or different-control endpoint do not participate.

With one candidate, apply it without requiring an edge. With multiple candidates, the
active graph must be acyclic and have exactly one terminal candidate with no outgoing
edge. Every other candidate must reach that terminal candidate. Apply the terminal
candidate. A cycle, no terminal candidate, or multiple terminal candidates is ambiguous
and must fail atomically; never select by SQL order, date, or lexical rationale order.
Branching paths may converge on one terminal decision and are valid.

## Service exception networks

The registry table `service_networks(profile, service_name, allowed_cidr)` limits
`SV-SERVICE-07` exception addresses. For each exception entry naming a service present in
the input, require a valid dotted-quad IPv4 address and at least one matching row for the
site's profile and service. The address must fall inside any one of that service's approved
CIDRs using normal IPv4 prefix semantics; multiple rows are alternatives and their SQLite
order has no meaning. Validate every CIDR row applicable to that profile and service before
selecting a match, so a malformed alternative remains fatal even beside a valid matching
row. A missing policy row, malformed address or CIDR, or address outside
every approved network is fatal and must preserve the existing bundle. Exception entries
for services absent from the input remain warnings and do not require a network row.

An applied service exception adds evidence identifying each matching
`sqlite:service_networks` row by its `allowed_cidr`, in addition to the runbook and
exception evidence already required. Use this exact evidence shape:

```json
{"source": "sqlite:service_networks", "key": "allowed_cidr", "value": "10.70.0.0/24"}
```

## Integrity manifest

After staging the other three artifacts, invoke the local `sha256sum` command to hash each
one. `bundle-manifest.json` uses this exact structure, with `files` sorted by `path`:

```json
{
  "algorithm": "sha256",
  "files": [
    {"path": "hardening-report.json", "sha256": "<lowercase 64-hex digest>"},
    {"path": "services.json", "sha256": "<lowercase 64-hex digest>"},
    {"path": "streamvault.yaml", "sha256": "<lowercase 64-hex digest>"}
  ],
  "root_sha256": "<lowercase 64-hex digest>"
}
```

Compute `root_sha256` with `sha256sum` over the UTF-8 bytes formed by concatenating one
line per sorted entry as `<sha256><two spaces><path><newline>`. The manifest itself is not
included in `files`. Emit the manifest as canonical JSON under the same atomic publication
boundary; a hashing failure must preserve the previous bundle.

## Warnings

Sort warning strings and use these exact templates:

- `ignored disabled camera <camera_id>`
- `ignored missing media fixture for camera <camera_id>: <fixture>`
- `ignored unsafe media fixture for camera <camera_id>: <fixture>`
- `ignored expired exception <rationale_id> for <control_id>`
- `ignored unauthorized exception <rationale_id> for <control_id>`
- `ignored exception service not present in input: <service_name>`

Symlinks and non-regular media entries are unsafe; absent entries are missing. Warnings
must not expose secret values, absolute host paths, timestamps, or nondeterministic data.

## Publication safety

Malformed YAML or JSON, missing inputs, unknown or ambiguous registry state, invalid ports
or retention bounds, and required-tool failures exit nonzero. Build the complete bundle in
a temporary sibling directory and publish it atomically. On failure, remove temporary
files and preserve any existing output directory byte-for-byte.

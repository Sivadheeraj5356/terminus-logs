# Zone Publisher Report Contract

`zone-publisher` writes one canonical UTF-8 JSON report to the `--report` path.

Reports are UTF-8 JSON with two-space indentation and exactly one trailing newline.
`format_version` is integer `1`.

## Top-level key order

```text
format_version
inputs
summary
findings
suppressed
candidate
```

`inputs` contains SHA256 digests for zone, journal, freezes, and exceptions, each
formatted as lowercase hex, under keys `zone_sha256`, `journal_sha256`,
`freezes_sha256`, and `exceptions_sha256` in that order.

Each digest is the SHA256 of the **raw input file bytes** at the path passed on the
command line. Digests are not computed from parsed records, sorted rows, or normalized
text. Reordering journal, freeze, or exception rows changes the corresponding digest
when the on-disk bytes change, even when the semantic publication outcome is unchanged.

Report determinism applies to `summary`, `findings`, `suppressed`, and `candidate` on
valid inputs with identical file bytes. Only the `inputs` digests vary when input file
bytes differ.

`summary` contains `publishable`, `findings`, `suppressed`, and `active_changes` in
that order. `publishable` is a JSON boolean. Counts are integers.
`publishable` is `true` only when `findings` is empty.

## Finding objects

Required finding object key order:

```text
zone
owner
record_type
code
severity
evidence
```

`findings` is sorted by `zone`, then `owner`, then `record_type`, then finding code.

## Suppressed objects

Required suppressed object key order:

```text
zone
owner
record_type
code
exception_id
reason
evidence
```

`suppressed` is sorted by `zone`, then `owner`, then `record_type`, then finding code,
then `exception_id`.

## Candidate object

Required candidate object key order:

```text
zone
soa_serial
record_count
delegation_count
```

`soa_serial` is an unsigned integer. `record_count` counts every RR remaining in the
candidate zone. `delegation_count` counts distinct non-apex owners that have at least
one NS record.

Empty arrays are rendered as `[]`. Evidence strings are stable and must not include
absolute temporary paths. Report content must be byte-identical across repeated runs on
the same valid inputs.

## Evidence strings

Each finding and suppressed entry carries one `evidence` string built from a fixed
phrase for the finding code. When a code lists a trailing detail token below, append one
ASCII space and that detail after the phrase. Do not add detail text for codes that do
not list one.

| Code | Evidence phrase | Trailing detail |
|---|---|---|
| `SERIAL_NOT_ADVANCED` | `candidate SOA serial is not advanced` | none |
| `APEX_CNAME` | `CNAME present at zone apex` | none |
| `SOA_COUNT` | `apex SOA count is not exactly one` | none |
| `CNAME_CONFLICT` | `CNAME owner has conflicting non-DNSSEC records` | none |
| `DELEGATION_GLUE_MISSING` | `in-zone delegated nameserver lacks glue` | absolute nameserver owner needing glue |
| `WILDCARD_BELOW_DELEGATION` | `wildcard owner lies below a delegated zone cut` | none |
| `FREEZE_WINDOW` | `active change overlaps freeze window` | `freeze_id` |
| `TXT_CANONICAL` | `TXT rdata is not in canonical form` | none |
| `TTL_OUT_OF_RANGE` | `TTL outside allowed range 30..86400` | none |
| `UNKNOWN_DELETE` | `delete targets a record absent from the candidate` | none |

For `DELEGATION_GLUE_MISSING`, the trailing detail is the in-zone delegated nameserver
name (for example `ns.child.example.`), not the delegation owner and not a wildcard
owner.

For `FREEZE_WINDOW`, the trailing detail is the matching freeze row `freeze_id`.

## Example report

The following populated example shows one blocking finding and one suppressed finding:

```json
{
  "format_version": 1,
  "inputs": {
    "zone_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "journal_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "freezes_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "exceptions_sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
  },
  "summary": {
    "publishable": false,
    "findings": 1,
    "suppressed": 1,
    "active_changes": 2
  },
  "findings": [
    {
      "zone": "example.com.",
      "owner": "www.example.com.",
      "record_type": "A",
      "code": "FREEZE_WINDOW",
      "severity": "blocking",
      "evidence": "active change overlaps freeze window FZ1"
    }
  ],
  "suppressed": [
    {
      "zone": "example.com.",
      "owner": "mail.example.com.",
      "record_type": "MX",
      "code": "FREEZE_WINDOW",
      "exception_id": "EX1",
      "reason": "mail cutover approved",
      "evidence": "active change overlaps freeze window FZ2"
    }
  ],
  "candidate": {
    "zone": "example.com.",
    "soa_serial": 2026010101,
    "record_count": 8,
    "delegation_count": 1
  }
}
```

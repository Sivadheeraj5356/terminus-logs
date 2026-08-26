# Zone Publisher Input Formats

This document defines the four input files consumed by `zone-publisher`.

## Zone snapshot text

The zone file contains one DNS resource record per non-empty line. Comment lines
start with `;` and are ignored. Owner names are absolute and end with `.`.

Supported record types:

```text
SOA
NS
A
AAAA
CNAME
MX
TXT
CAA
DS
DNSKEY
RRSIG
NSEC
```

Each zone RR uses this field layout:

```text
owner ttl class type rdata...
```

Required RR constraints:

```text
class must be IN
ttl must be an integer from 30 through 86400
owner must be an absolute name ending in .
```

SOA rdata is written as:

```text
mname rname serial refresh retry expire minimum
```

## Change journal NDJSON

Each non-empty line is one JSON object with these keys:

```text
change_id
seq
action
zone
owner
ttl
record_type
rdata
effective_utc
correction_of
reason
```

Allowed actions:

```text
add
delete
replace
```

`ttl` is an integer. For `delete`, `ttl` may be `0` and `rdata` must still identify
the exact record being removed. `correction_of` is an empty string when the record
is not a correction.

## Freeze CSV

Header (exact and ordered):

```text
freeze_id,zone,owner_suffix,record_type,start_utc,end_utc,reason
```

## Exception CSV

Header (exact and ordered):

```text
exception_id,zone,owner_suffix,record_type,code,start_utc,end_utc,reason
```

Allowed finding codes:

```text
SERIAL_NOT_ADVANCED
APEX_CNAME
SOA_COUNT
CNAME_CONFLICT
DELEGATION_GLUE_MISSING
WILDCARD_BELOW_DELEGATION
FREEZE_WINDOW
TXT_CANONICAL
TTL_OUT_OF_RANGE
UNKNOWN_DELETE
```

## Shared validation rules

CSV headers are exact and ordered. All timestamps are RFC3339 UTC strings ending in
`Z`. NDJSON records must be valid JSON objects, one object per line. Unknown actions,
unknown record types, unknown finding codes, missing required fields, invalid
timestamps, malformed TTLs, and malformed owner names are fatal.

Journal records are keyed by `change_id`; when multiple records share a `change_id`,
the highest `seq` is the active record. Two active records with the same `change_id`
and same `seq` are fatal. A record with `correction_of` refers to the corrected change
id; the corrected record replaces the referenced change only when its sequence is
higher.

Input row order must not affect valid report content. Reordering journal, freeze, or
exception rows with the same semantic content must produce an identical report body for
`summary`, `findings`, `suppressed`, and `candidate`.

Reordering rows may change the raw input file bytes and therefore the `inputs`
digests in the report. Row-order invariance does not apply to `inputs.*_sha256`.

An owner name matches an `owner_suffix` when it is exactly equal to the suffix or is
a descendant below that suffix. `record_type` value `*` in freeze or exception CSV
matches every supported record type.

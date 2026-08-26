# Evidence and report FORMATS

Layout reference for the meter-fraud case corpus and the report the audit writes. This file
is a format sheet only: it lists paths, field tables, the binary record layout, the file
grammars, the output line schemas, the database schema and the HTTP response shapes. It says
nothing about what any of it means or how anything is computed - the audit's rules are in
RULES.md in this directory.

## Corpus layout

    <data>/registry.json          the network registry
    <data>/exports/<name>.seg     packed binary meter-export segments
    <data>/circulars/<name>.txt   the regulator's circular book
    <data>/disputes.jsonl         settlement dispute rulings

`<data>/example` is a small corpus of the same shape.

## registry.json

    {
      "utilities": [{"id":"<3 letters>","utc_offset_min":<int>,"code":<u16>}, ...],
      "feeders":   [{"id":"<id>","utility":"<owner utility id>","code":<u16>}, ...],
      "points":    [{"id":"<id>","feeder":"<feeder id>","utility":"<owner utility id>",
                     "category":"residential"|"commercial"|"industrial",
                     "code":<u16>}, ...],
      "accounts":  [{"id":"<id>","parent":<account id>|null,"class":<1..4>,
                     "allowance_kwh":<int>,"code":<u32>,"serial":"<serial>"}, ...],
      "bands":     [{"from_kwh":<int>,"rate_cents":<int>}, ...],
      "standing":  {"<category>":{"<class>":<cents>, ...}, ...},
      "shed":      {"window_draws":<int>,"enter_kwh":<int>,"exit_kwh":<int>},
      "condemn_threshold": <int>,
      "penalty_cents": <int>,
      "replay_window_sec": <int>,
      "transfer":  [{"a":"<point id>","b":"<point id>","min_sec":<int>}, ...]
    }

A utility is a reporting/operating party; `utc_offset_min` is its fixed local-time offset
from UTC in minutes (may be negative, need not be a whole hour). A feeder is a physical
circuit owned by one utility. A delivery point is a metering point on a feeder. An account is
a supply contract; `parent` names another account, or is null. `allowance_kwh` is an energy
grant in kWh; `class` is a tariff class 1..4. `bands` is ascending by `from_kwh`, its first
entry at 0. `standing` is cents keyed by point category then tariff class. `transfer` lists
every unordered pair of delivery points exactly once. All ids, serials and numeric wire codes
are unique. Timestamps are UTC epoch seconds throughout the corpus.

## Meter export segments (`exports/<name>.seg`)

Packed binary, mixed-endian, no alignment padding.

Segment header, 14 bytes:

    offset  size  field
    0       4     magic "MEX1" (ASCII)
    4       2     record count, big-endian u16
    6       4     window base, little-endian u32 (UTC epoch seconds)
    10      2     sequence stamp, opaque carrier bytes
    12      2     header checksum, big-endian u16, computed like a record checksum over
                  the 14 header bytes with this field zeroed

Records follow back to back. One record, 20 + serial-length bytes:

    offset  size  field
    0       4     account code, little-endian u32 (0 on serial-keyed records)
    4       2     delivery point code, big-endian u16
    6       2     reporting utility code, little-endian u16
    8       4     timestamp offset, little-endian u32 (added to the window base)
    12      1     flag byte (bit layout below)
    13      1     serial length, u8 (0 on telemetry records)
    14      var   meter serial, ASCII, serial-length bytes
    +0      2     energy drawn in kWh, big-endian u16
    +2      2     sequence stamp, opaque carrier bytes
    +4      2     record checksum, big-endian u16

Flag byte:

    bits 0-1   source: 0 telemetry, 1 estimate, 2 manual
    bits 2-4   the reporter's claimed tariff class
    bit  5     field-inspection marker

Checksum encoding (header and record alike): XOR the big-endian 16-bit words of the buffer,
taken with the checksum field itself zeroed and an odd trailing byte padded with 0x00, then
exchange the high and low nibble of each of the two result bytes.

Every record in a segment names the same reporting utility, and the first record of a segment
is always intact. A segment's body may end before its header count is exhausted.

Annotated layout, `<data>/example/exports/export-01.seg`, 77 bytes, header count 4:

    4d 45 58 31             magic "MEX1"
    00 04                   record count 4 (big-endian)
    00 b9 55 69             window base 1767225600 (little-endian)
    02 0b                   sequence stamp (opaque)
    24 ba                   header checksum
    -- record 0, 20 bytes --
    71 11 01 00             account code 0x00011171 (little-endian)
    02 59                   delivery point code 0x0259 (big-endian)
    29 23                   reporting utility code 0x2329 (little-endian)
    78 69 00 00             ts offset 27000 (little-endian) -> ts 1767252600
    08                      flags: source 0 (telemetry), claimed class 2, no marker
    00                      serial length 0
    00 0f                   energy 15 kWh (big-endian)
    01 02                   sequence stamp (opaque)
    a2 f0                   record checksum

Record 0's checksum encoding, worked: the ten big-endian words of the record with the
checksum field zeroed are 7111 0100 0259 2923 7869 0000 0800 000f 0102 0000; their XOR is
2a0f; exchanging the nibbles within each byte gives a2f0, the stored value.

## Circular files (`circulars/<name>.txt`)

    GRID REVENUE PROTECTION CIRCULAR
    REF: <unique id>
    ISSUER: <utility id> | REGULATOR
    ISSUED: <UTC epoch seconds>
    EFFECTIVE: <start> [TO <end>]
    SUPERSEDES: <ref>[, <ref>...]

    <narrative paragraphs>

    DIRECTIVES:
    <one directive per line>
    END DIRECTIVES

    <narrative paragraphs>

The header is the contiguous block of `KEY: value` lines immediately after the title line.
REF, ISSUER, ISSUED and EFFECTIVE always appear; SUPERSEDES only on circulars that name
others. A circular carries at most one DIRECTIVES block and may carry none. Directive forms:

    BANDS <supply point account id> <from>:<rate> [<from>:<rate> ...]
    BANDS ALL <from>:<rate> [<from>:<rate> ...]
    STANDING <point category> <class>:<cents> [<class>:<cents> ...]
    SHED <supply point account id> WINDOW <n> ENTER <kwh> EXIT <kwh>
    EXEMPT <account id>

A BANDS directive's tier list has the same shape as the registry `bands`: `from` ascending,
first `from` 0. Directives always name registered accounts, supply points and categories, and
a circular never carries two directives on the same subject.

## disputes.jsonl

One JSON object per line:

    {"id":"<id>","draw":"<draw id>","filed_by":"<utility id>","basis":"<circular ref>",
     "filed_ts":<int>,"ruling":"upheld"|"rejected","ruled_ts":<int>}

At most one ruling names any given draw.

## Report files

Every report file is compact JSON - no spaces between tokens - with every line terminated by
LF. Object keys appear in exactly the order shown.

`<out>/evidence.jsonl`, one line per record:

    {"segment":...,"record":...,"utility":...,"account":...,"point":...,"ts":...,
     "source":...,"class":...,"kwh":...,"inspect":...}

`source` is the string `telemetry`, `estimate` or `manual`; `inspect` is a boolean.

`<out>/intake.json`, one line:

    {"segments":...,"records":...,"reads":...,"tampered":...,"lost":...,"unresolved":...,
     "findings":...,"findings_by_kind":{...},"utilities":[...],
     "evidence_digest":"<8 lowercase hex>","findings_digest":"<8 lowercase hex>"}

`findings_by_kind` carries the keys `tamper`, `spoliation`, `misdeclare`, in that order.
Each entry of `utilities` is

    {"utility":...,"reads":...,"tamper":...,"lost":...,"misdeclare":...,"flagged":...,
     "leakage_cents":...,"exposure_cents":...}

`<out>/draws.jsonl`, one line per draw:

    {"id":...,"ts":...,"point":...,"operator":...,"feeder":...,"account":...,"home":...,
     "class":...,"source":...,"reads":...,"kwh":...,"status":...}

`status` is one of the strings `ok`, `replay`, `bypass`, `suspect`.

`<out>/draws.json`, one line:

    {"draws":...,"excluded":...,"by_status":{"ok":..,"replay":..,"bypass":..,"suspect":..},
     "compromised_accounts":[...],"findings":...,"findings_by_kind":{...},
     "draws_digest":"<8 hex>","findings_digest":"<8 hex>"}

`findings_by_kind` here carries the keys `tamper`, `spoliation`, `misdeclare`, `replay`,
`bypass`, `quarantine`, in that order.

`<out>/register.jsonl`, one line per settled draw:

    {"id":...,"ts":...,"point":...,"operator":...,"feeder":...,"account":...,"home":...,
     "root":...,"class":...,"source":...,"reads":...,"peak":...,"shed":...,"kwh":...,
     "admitted":...,"standing_cents":...,"toll_cents":...,"charged_cents":...,"status":...}

`peak` and `shed` are booleans; `status` is one of the strings `ok`, `replay`, `bypass`,
`suspect`, `voided`, `severed`.

`<out>/findings.jsonl`, one line per finding, fields per kind in exactly this order:

    {"kind":"tamper","utility":...,"segment":...,"record":...,"cents":...}
    {"kind":"spoliation","utility":...,"segment":...,"lost":...,"cents":...}
    {"kind":"misdeclare","utility":...,"segment":...,"record":...,"account":...,
     "claimed":...,"registry":...,"cents":...}
    {"kind":"replay","account":...,"home":...,"draw":...,"prior":...,"gap_sec":...,
     "cents":...}
    {"kind":"bypass","account":...,"home":...,"draw":...,"conflict":...,"gap_sec":...,
     "bound_sec":...,"cents":...}
    {"kind":"quarantine","account":...,"home":...,"from_ts":...,"draws":...,"cents":...}
    {"kind":"void_fraud","dispute":...,"filed_by":...,"draw":...,"basis":...,"cause":...,
     "cents":...}
    {"kind":"condemnation","feeder":...,"utility":...,"excluded":...,"severed":...,
     "cents":...}

`cause` is one of the strings `unknown`, `superseded`, `expired`.

`<out>/summary.json`, one line:

    {"case":{...},"exposure":[...],"supply":[...],"register_digest":"<8 hex>",
     "audit_digest":"<8 hex>","findings_digest":"<8 hex>"}

    case:     {"draws":...,"excluded":...,"reads":...,"tampered":...,"lost":...,
               "findings":...,"findings_by_kind":{...},"compromised_accounts":[...],
               "condemned_feeders":[...],"severed_accounts":[...],"charged_cents":...,
               "leakage_cents":...,"exposure_cents":...,"top_utility":...}
    exposure: [{"utility":...,"reads":...,"tamper":...,"lost":...,"misdeclare":...,
                "flagged":...,"replay":...,"bypass":...,"suspect":...,"severed":...,
                "void_fraud":...,"condemned_feeders":...,"leakage_cents":...,
                "exposure_cents":...}, ...]
    supply:   [{"root":...,"utility":...,"accounts":...,"draws":...,"admitted_kwh":...,
                "charged_cents":...,"shed_draws":...,"final_headroom":...}, ...]

`case.findings_by_kind` carries all eight kinds as keys, in the order `tamper`,
`spoliation`, `misdeclare`, `replay`, `bypass`, `quarantine`, `void_fraud`, `condemnation`.

## The case-file database

    CREATE TABLE register (id TEXT PRIMARY KEY, ts INTEGER, point TEXT, operator TEXT,
        feeder TEXT, account TEXT, home TEXT, root TEXT, class INTEGER, source TEXT,
        reads INTEGER, peak INTEGER, shed INTEGER, kwh INTEGER, admitted INTEGER,
        standing_cents INTEGER, toll_cents INTEGER, charged_cents INTEGER, status TEXT);
    CREATE TABLE findings (seq INTEGER PRIMARY KEY, kind TEXT, body TEXT);

## HTTP response shapes

    GET /register        -> {"register":[<register object>, ...],"count":<int>}
    GET /register/{id}   -> <register object>            (404 on an unknown id)
    GET /findings        -> {"findings":[<finding object>, ...],"count":<int>}

A register object carries exactly the fields of a `register.jsonl` line, in that order; a
finding object exactly the fields of a `findings.jsonl` line, in that order. A 404 body is
a JSON object. Query parameters: `min_charge`, `status` on `/register`; `kind` on
`/findings`.

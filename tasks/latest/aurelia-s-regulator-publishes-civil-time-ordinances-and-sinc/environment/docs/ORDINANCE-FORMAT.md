# Ordinance record format

Published by the Aurelian Bureau of Standards. One record per file, named after the
ordinance identifier, under a directory named for the jurisdiction it applies to.

## Record

Records are line oriented and UTF-8. A line is a field name, a colon, and a value.
Blank lines and lines whose first non-space character is `#` are ignored. Field names
do not repeat within a record.

An `observance:` field takes no value on its own line; the two lines that follow it
are indented by exactly two spaces and carry the keys `begin` and `end`.

## Fields

| Field | Cardinality | Value |
| --- | --- | --- |
| `ordinance` | required | `ORD-<year>-<seq>`, where `<seq>` is two digits |
| `jurisdiction` | required | the publishing jurisdiction |
| `enacted` | required | `YYYY-MM-DD`, the date the ordinance was passed |
| `effective` | required | an anchored instant (below) |
| `standard-offset` | establishing only | an offset, or `basis <ordinance>` |
| `standard-label` | establishing only | an abbreviation, or the keyword `numeric` |
| `observance` | optional | a seasonal recurrence pair |
| `repeals` | repeal only | the identifier of the ordinance it repeals |

A record that carries `repeals` is a **repeal ordinance**: it establishes no offset,
carries no observance, and names exactly one ordinance. Every other record is an
**establishing ordinance**.

## Offsets

`+HH:MM:SS` or `-HH:MM:SS`, east of the prime meridian positive. An observance's
`save` uses the same syntax and may be negative.

## Anchored instants

An `effective` value is `YYYY-MM-DDThh:mm:ss` followed by whitespace and one of the
anchor keywords `wall`, `standard`, or `universal`. The date and time are civil, not
UT, except under the `universal` anchor. The hour field may exceed 23.

An ordinance's `effective` instant may precede its `enacted` date.

## Observance events

Each of `begin` and `end` is:

```
<month> <day-specifier> <hh:mm:ss> <anchor> [save <offset>] [label <abbrev>]
```

`<month>` is a three-letter English abbreviation, `Jan` through `Dec`.

The day specifier is one of:

| Form | Denotes |
| --- | --- |
| `lastSun` | the last Sunday of the month; any weekday abbreviation is accepted |
| `Sun>=8` | the first Sunday falling on or after the eighth |
| `Sun<=25` | the last Sunday falling on or before the twenty-fifth |
| `d17` | the seventeenth, whatever weekday it is |

The time of day may be `24:00:00` or greater; such a value denotes an instant in a
following day, month, or year.

On `begin`, `save` defaults to `+01:00:00` and `label` is required. On `end`, `save`
defaults to `+00:00:00` and `label` defaults to the record's `standard-label`.

## Jurisdiction metadata

`meta.toml` in each jurisdiction's directory:

| Key | Cardinality | Value |
| --- | --- | --- |
| `zone` | required | the jurisdiction name |
| `meridian_seconds` | required | the jurisdiction's meridian, in seconds east |
| `inherits` | optional | a dissolved jurisdiction this one succeeds |
| `inherits_before` | with `inherits` | `YYYY-MM-DD`, the succession date |

Where `inherits` is present, the succeeding jurisdiction's corpus also comprises the
named jurisdiction's ordinances whose `enacted` date falls strictly before
`inherits_before`. Those records keep their original identifiers.

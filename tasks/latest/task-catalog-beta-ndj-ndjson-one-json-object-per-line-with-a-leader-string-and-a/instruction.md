## Task
Read each shelf under /app/shelves and emit one JSON envelope at /app/output/report.json.

## Shelf formats
catalog_alpha.mrk (MARK text): each line starts with equals, three char tag, two spaces, then the 24 char leader when the tag is LDR, or two indicators plus dollar delimited subfields for data tags. Blank line ends a record.

catalog_beta.ndj (NDJSON): one JSON object per line with a leader string and a fields array. A field is either control (tag plus value) or data (tag, ind1, ind2, subfields array of code and value).

catalog_gamma.fwt (fixed width): leader lines are `LEADER:` followed by the 24 char leader. Field lines are `TAG=nnn LEN=llll OFFS=ooooo DATA=body` where body is two indicators plus dollar subfields for data tags. `ENDREC` ends the record.

## Envelope
Top keys in order: report_digest, schema_version equal marc-classifier-v1, records, by_verdict, summary. Record keys: shard, record_seq, field_seq, tag, verdict, pin_consumed. Summary keys: total_records (emitted row count, not source MARC records), pin_consumed_count, cascade_arms_total. Sort by shelf alpha, beta, gamma then record_seq then field_seq. Digest is sixteen hex of sha256 over Go json marshal of records, by_verdict, summary. Emit one leader row at field_seq one tagged LDR then one row per field. Ten verdicts in /app/catalog/report_shape.json.

## Rules
Tags are three digits, control 001-009, data 010-999, else TAG_OUT_OF_RANGE. Indicators are space, digit, or lower alpha, else INDICATOR_NONBLANK_REJECTED. Data fields need a dollar subfield delimiter, else SUBFIELD_DELIMITER_MISSING. Two identical tags back to back inside one record drop the second to DUPLICATE_TAG_DROPPED. Leader positions 12-16 must be digits, else LEADER_BASE_ADDR_INVALID. Leader position 9 is a or space; a bad nine becomes ENCODING_PIN_RESCUED when the seal under /app/seals equals the first sixteen hex of HMAC-SHA256 key marc-pin-v1 over shard|record_seq, else LEADER_BASE_ADDR_INVALID.

## Cascade
Per shelf, count TAG_OUT_OF_RANGE cumulatively; the counter never resets on other verdicts or across records inside the shelf. When it hits two, the next CONTROL_FIELD_ACCEPTED or DATA_FIELD_ACCEPTED becomes CASCADE_QUARANTINED; that single demotion resets both the armed flag and the counter for that shelf. Binary at /app/bin/marcrec.

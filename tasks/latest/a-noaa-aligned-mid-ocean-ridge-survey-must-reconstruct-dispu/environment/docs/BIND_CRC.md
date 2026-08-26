# Bind CRC contracts

All bind digests use CRC32 over UTF-8 input bytes, formatted as 8 character lowercase hexadecimal with no 0x prefix.

The CRC32 value is a 32-bit unsigned integer. Render it as exactly eight hexadecimal characters, padding on the left with zero characters when the value is small. A digest is always eight characters wide, so a value like 0x00abcdef is written as 00abcdef, never as abcdef.

## staging_bind

Canonical sorted-key JSON of the object:

{"expedition_id":"<id>","report_ids":["<sorted report_id strings from bundle reports array>"]}

report_ids must be sorted ascending lexicographically before hashing.

## lane_bind

Plain UTF-8 string, not JSON.

Sort winning report_id values ascending. Join with semicolon. Append one final semicolon after the last id.

Form: report_a;report_b;

Example with winners nt-003 and sr-002: nt-003;sr-002;

Do not omit the trailing semicolon.

## reconcile_bind

Canonical sorted-key JSON of an array built from feature_links in timestamp survivor order (skip the first observation).

Each array element is an object with keys links_to and obs_id (canonical JSON sorts keys alphabetically).

Example element: {"links_to":"obs-001","obs_id":"obs-003"}

## expedition_seal

expedition_seal is the CRC32 digest, formatted as eight character lowercase hexadecimal, of a plain UTF-8 string. The string is atlas_witness, then a single pipe character, then reconcile_bind.

Input string form: atlas_witness + "|" + reconcile_bind

The joined string is only the input to CRC32. Do not emit the joined string as the expedition_seal value. Hash it with CRC32 like every other bind digest and emit the eight character lowercase hex result.

Example: if atlas_witness is 1a2b3c4d and reconcile_bind is 00fe12ab, hash the string 1a2b3c4d|00fe12ab and write the resulting eight character hex digest as expedition_seal.

reconcile_bind must be read from /app/state/{expedition_id}-reconciled.json, not recomputed from the --observations CLI path alone.

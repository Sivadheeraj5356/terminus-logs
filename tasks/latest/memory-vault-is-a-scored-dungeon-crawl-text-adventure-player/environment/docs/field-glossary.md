# Field glossary

- `sha16` — the first 16 lowercase hexadecimal characters of a SHA-256 digest.

- `generation` / `hazard.epoch` — `sha16` of the live chamber ledgers as raw
  bytes: `/app/environment/traces/watch-chambers.log`, then one LF byte
  (`0x0A`), then `/app/environment/traces/scrub-chambers.txt`. Do not normalize
  either file or insert any other separator.

- `moves_fp` — `sha16` of the adventure’s filtered move-script lines joined by
  LF (non-empty lines after stripping, excluding `#` comments).

- `trace_hash` — `sha16` of a UTF-8 preimage made of these eight segments in
  order, each separated by one LF (no trailing LF after the last segment):

  1. `case_id`
  2. every filtered move-script line joined by LF, including filtered commands
     that occur after the first `EXIT`
  3. final status (`WIN` / `LOSE` / `PARTIAL`)
  4. visited rooms joined with `>`
  5. lexically sorted inventory joined with `,`
  6. violations in play order joined with `,`
  7. `W:` followed by lexically sorted watched rooms joined with `,`
  8. `L:` followed by lexically sorted leak rooms joined with `,`

  Campaign `generation` is not part of this preimage.

- `COMMIT` — save-log marker that permits transcript publication.

- `WIN` / `LOSE` / `PARTIAL` — adventure outcome labels in each transcript.

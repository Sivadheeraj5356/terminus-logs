# Campaign save log

Path: `/app/output/state/replay.journal`

Line-oriented records (UTF-8), one record per line:

- `GEN|<generation>` — hazard generation for this campaign
- `START|<case_id>|<moves_fp>|<generation>` — adventure begins
- `EVT|<case_id>|<seq>|<command>` — applied gameplay command
- `FIN|<case_id>|<status>|<score>|<violations>` — adventure finalized
- `COMMIT|<case_id>` — adventure committed; transcript may be published
- `END` — campaign closed after all current adventures commit

Rules:

1. Only committed adventures may appear in published transcripts/manifest.
2. An interrupted adventure (START without COMMIT) must be rolled back or
   safely replayed; partial transcripts must not remain authoritative.
3. Previously COMMIT records may be reused only when `moves_fp` and
   `generation` still match the live inputs.
4. Changing one `.moves` file retires that adventure. Changing the watch or
   scrub ledger files under `/app/environment/traces/` produces a new
   generation and retires every adventure.
5. Adding/removing case files must update the manifest and delete stale
   transcripts for missing case ids.
6. Commands after the first `EXIT` must not change game state and must not be
   written as `EVT` records.
7. A truncated final save-log line (no trailing newline) may be discarded and
   the campaign continued. A non-record line in the middle of committed
   history must fail with a non-zero exit and leave the last valid published
   `batch.manifest.json` unchanged.
8. Transcripts and the manifest must be written via temporary files then
   replaced in place. Publish the manifest only after every current adventure
   is committed and every transcript matches the same generation.
9. Manifest cases are listed in lexical `case_id` order and include each
   adventure's move-script fingerprint and generation.

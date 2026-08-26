# Journal tip chain

`journal_tip_hex` is not a single FNV over the raw journal file bytes.

For each complete line `L` in `$STAGE_ROOT/journal/<manifest_id>.frames` (including its trailing newline), compute the 8-hex FNV-1a digest of `L`. Concatenate those digests in file order with no separators. The tip is the 8-hex FNV-1a of that concatenation.

Empty journal → tip of FNV-1a over the empty string → `811c9dc5`.

The same tip algorithm applied to the journal **before** a fold appends yields `parent_tip` for the secondary digest half in `docs/stage_rules.md`. The certificate field `journal_tip_hex` always uses the tip **after** that fold's append.

Historical probes that hashed the entire file blob in one shot disagree with this chain and must not be used for graded tips or parent tips.

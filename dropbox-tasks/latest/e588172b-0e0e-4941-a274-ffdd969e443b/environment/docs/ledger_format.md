# Schedule ledger format

The offline rebuild ends in a single JSON file at /app/output/schedule_ledger.json. Operators use it as the authoritative schedule history for each daylight-saving transition window, together with a digest that ties the file to a particular stepped tree.

## Row shape

Each element of the rows array describes one reconciled host schedule interval. The cycle field is the cadence index for that interval. The window field names which seasonal discontinuity produced the row: backward for autumn fall-back, forward for spring forward, or resume for post-restart catch-up. The civil_key field is the canonical calendar coordinate, either an eight-digit YYYYMMDD day key or a ten-digit YYYYMMDDHH hour key when a specific civil hour matters. The shipped windows use values such as 20231105 for the autumn day, 2024031002 and 2024031202 for spring absent hours, and 20240311 together with 20240312 for resume catch-up fragments. wall_offset counts SI seconds into the affected local hour, seq is the run ordinal inside that window, and octets is the folded payload byte tally.

## Digest

The ledger_digest field stores a lowercase SHA-256 hex string over a canonical text form of the rows. Each row becomes one line formatted as cycle,window,civil_key,wall_offset,seq,octets. Those lines are sorted lexicographically, joined with newline characters, and the blob is terminated with a final newline before hashing. The same computation can be checked with any standards-compliant SHA-256 tool, for example openssl dgst -sha256 fed the canonical line blob.

Packing the same stepped tree twice therefore yields the same digest, while editing a row without re-stepping the affected window changes the digest away from the value a clean regeneration would produce.

## Window behaviour in practice

The backward window covers autumn fall-back, when the local clock repeats an hour. In a healthy regeneration it still emits one row per civil day because repeat_guard and repeat_slot_sec from m5s/cadence_policy.conf govern how repeated wall slots are folded. The lane rebinds slot state before every fragment, so the last fire instant must be remembered in slot_state.rec inside that window's out directory; process-local memory alone is not enough. Without that durable state the two repeated-hour fragments both land in the ledger as separate completed runs for the same YYYYMMDD day, and a later step_tool invocation over the same tree cannot recognize the repeat either.

The forward window covers spring forward, when one civil hour never occurs on the wall clock. The history still carries that interval: you will see a day-level row plus an hour-level row whose final two digits name the absent hour. n2h/missing_hours.tab is the lookup table the forward lane consults; it returns both a status code and an exists flag, and an hour marked absent on the wall is still represented in the ledger rather than dropped silently. When a later window revisits the same civil day, the commit log already carries any finer hour-level key produced by an earlier window. Operators treat that hour-level key as the authoritative coordinate for the day when reading the packed history alongside resume catch-up rows.

The resume window covers restarts. Two passes exist, and they are not interchangeable.

On the initial regeneration, boot_era.rec does not exist yet when stepping begins. The first pass walks every captured fragment once and emits every fragment that belongs in the snapshot, including timezone-skip fragments (flag bit 0x04 in u4r/sweep_trace_format.txt) and boot-gap fragments (wall_offset at or above 86400). Those boot-gap rows are first-pass work: they use seq below 100. Naming a fragment a boot gap describes its wall_offset signal only; it does not mean the row is recovery catch-up on the initial run. The recovery pass in that same initial step sees no boot-era marker yet, so it emits nothing. After the resume step finishes, boot_era.rec is bumped to a generation of at least one.

Recovery rows (seq at or above 100) appear only on a later resume step, after boot_era.rec already exists from a previous complete resume. On that later step the first pass leaves boot-gap fragments for recovery when the era marker is already present. Recovery then emits an uncommitted boot-gap interval exactly once, skips any fragment already recorded in /app/output/step/commit_log.tab, and skips timezone-skip fragments that already have their first-pass row. A clean initial regeneration therefore ends with two first-pass resume rows and zero recovery rows.

Worked example — warm resume re-step: after a successful cold rebuild, boot_era.rec is at least 1. Invoking step_tool again on the resume pane must rewrite that pane's rows.tab to a single first-pass timezone-skip row (for example civil_key 20240311). The boot-gap fragment stays deferred on the first pass solely because the era marker is already present—not because of the commit log. If commit_log.tab still lists that boot-gap key from the cold run, the later recovery pass also stays quiet for it; if the commit log was cleared while the era remained warm, recovery may emit that uncommitted boot-gap interval once (seq at or above 100). Packing the unchanged stepped tree twice is a separate rule and still yields the same ledger_digest.

## Shared schedule state

During one regeneration run, every row emission appends a tab-separated line to /app/output/step/commit_log.tab with the window name, civil_key, seq, and flags. Later windows and the resume recovery pass read that log before emitting again. The log persists across consecutive step_tool calls until the step tree is cleared.

boot_era.rec is written at the end of a resume step. That is why the file is absent until resume has finished during a staged regeneration, and why recovery cannot emit on the initial pass even though first-pass boot-gap rows are already present.

## How the file is produced

The JSON is meant to be the output of stepping each window and then running pack_tool. Direct edits to schedule_ledger.json or to a window's rows.tab without re-stepping that window leave the digest inconsistent with the row set. The regenerate commands live in step_tool.md.

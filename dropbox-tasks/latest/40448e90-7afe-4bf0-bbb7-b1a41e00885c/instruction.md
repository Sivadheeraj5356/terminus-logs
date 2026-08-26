Image promotion across three supply-chain profiles is producing inconsistent
`/app/output/kv_export.json` reports. Content fingerprints disagree with the
trust authority, stage transcripts fail replay checks, some runs disappear from
the session export, and a mid-session loss of `/app/state/mirror_view.json` no
longer yields the same export as an uninterrupted run—especially while a replica
lag profile is still catching up.

The pipeline lives under `/app/environment`. Stage binaries, rebuild, and run
order are in `/app/environment/docs/matrix_cmds.md`. Hand-written JSON is
insufficient; the verifier clears outputs and regenerates them through the
normal pipeline.

The export carries profiles, runs, and report_digest. Each run row includes
role_version, content_digest, delegation_expiry, and stage_transcript_hex.
Behavioral rules for stage binding, mirror promotion, ledger durability, lane
quorum, transcript assembly, session export, and mirror-view recovery are in
`/app/environment/docs/stage_contract.md` and
`/app/environment/docs/row_export.md`. Profile timelines are in
`/app/environment/docs/seed_timelines.md`.

Update the sources under `/app/environment` so uninterrupted sessions and
sessions that lose `/app/state/mirror_view.json` mid-run both produce a correct,
consistent `kv_export.json` for the seed timelines.

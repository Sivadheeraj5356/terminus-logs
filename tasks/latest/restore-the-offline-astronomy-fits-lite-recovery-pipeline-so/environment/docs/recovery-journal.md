# Recovery journal records

`/app/data/journal/resume.tsv` is an immutable record of the interrupted run.
`PREPARE` records describe staged tile work. `COMMIT` records count only when
they match the next tile in `/app/data/tile-order-authority.tsv`; later
prepared records or out-of-prefix commits are discarded during recovery and are
reported in `rolled_back_records`.

Recovery publishes a complete mosaic for every authority tile. Re-running
recovery over an already complete work directory must not duplicate tile ids or
change the published semantic state.

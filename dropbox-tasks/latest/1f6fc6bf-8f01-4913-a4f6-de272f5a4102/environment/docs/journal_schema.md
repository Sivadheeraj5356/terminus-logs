# Journal schema

`/output/pool_journal.csv` header:

`socket_id,shard,event,pool_generation,round_index`

`pool_generation` is the post-increment ledger value after `mark_populated()` for the populate pass that produced the run. Rows are sorted by ascending `round_index` then ascending `socket_id`.

Events include `linger_reclaim` after idle reconciliation.

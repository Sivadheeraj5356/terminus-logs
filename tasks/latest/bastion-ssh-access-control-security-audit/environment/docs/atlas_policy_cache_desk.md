# Atlas policy cache desk (draft — not ratified)

`bastion:registry:cache:atlas` carries stale `Compression no` and `TCPKeepAlive no`. Production ingest must read `bastion:overrides:tenant:atlas` only.

# Fighting-game workspace notes

Background only; `duel_rules.md` and `session_semantics.md` are authoritative.

The duel is a small competitive fighting game: movement and combat crates own
the tick physics, and the online crates own how a predicting client stays in
sync when remote stick inputs arrive late. Determinism is the whole point of
match play: host and client must agree on the six-byte layout and tick order.

`bench::batch_replay_digest` is an offline helper that assumes both inputs are
known. It is not wired into the match runner.

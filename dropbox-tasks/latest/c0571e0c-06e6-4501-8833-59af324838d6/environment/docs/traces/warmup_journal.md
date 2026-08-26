# Warmup frame journal (delay=1)

Normative example for session_semantics.md.

| frame | confirms_tick | confirmed_after | remote_used | rollbacks |
|------:|--------------:|----------------:|------------:|----------:|
| 0 | - | -1 | 0 | 0 |
| 1 | 0 | 0 | 1 | 1 |
| 2 | 1 | 1 | 1 | 1 |
| 3 | 2 | 2 | 8 | 2 |
| 4 | 3 | 3 | 4 | 3 |
| 5 | 4 | 4 | 4 | 3 |
| 6 | 5 | 5 | 4 | 3 |
| 7 | 6 | 6 | 8 | 4 |
| 8 | flush | 7 | - | 5 |

Before any tick is confirmed the client uses remote byte 0. After tick r
is confirmed, unconfirmed ticks repeat inputs[r].remote until they confirm.

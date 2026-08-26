# Fixture schema

Labs copy immutable fixtures before bootstrap.

`fixtures/users.db` rows are `USER|PASSWORD|recovery_password_result` where `recovery_password_result` is `auth_err` or `ignore`.

`fixtures/tokens.db` rows are `TOKEN_ID|USER|SECRET`. Labs may define paired collision and main recovery secrets for the same user, plus an additional ordinary user for cross-session occupancy checks.

The bundled public fixtures use users `alice`, `bob`, and `carol` with passwords `correct-horse`, `battery-staple`, and `delegated-pass`. `alice` uses `recovery_password_result=auth_err` with recovery tokens `main-token` and `collide-token`; `carol` uses `recovery_password_result=ignore` with recovery token `carol-token`.

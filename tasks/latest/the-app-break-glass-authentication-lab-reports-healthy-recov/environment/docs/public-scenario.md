# Public verification scenario

`/app/scripts/verify-public.sh` exercises user `alice` (`recovery_password_result=auth_err`) with password `correct-horse`, recovery secrets `main-token` and `collide-token`, and session ids including `alice-r1`, `occupied`, and `bob-normal`. After the collision attempt against an occupied session, token `A-COLLIDE` stays `fresh` and token `A-MAIN` ends `consumed` with `audit.denied` at six for `alice`.

The same script then exercises user `carol` (`recovery_password_result=ignore`) with password `delegated-pass` and recovery secret `carol-token`. After three password failures, lockout denial, successful recovery login/logout, and replay denial, token `C-MAIN` ends `consumed` with `audit.denied` at five for `carol`.

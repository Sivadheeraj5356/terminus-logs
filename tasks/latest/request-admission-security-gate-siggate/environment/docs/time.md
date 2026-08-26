# Time window

`CREATED_DECIMAL` / `EXPIRES_DECIMAL` are the envelope integers rendered in
decimal with no sign and no leading zeros (except the value `0` itself).

Verification at unix seconds `now`:

- If `expires < created`, fail `invalid_window`.
- Otherwise accept iff `created ≤ now ≤ expires` (closed on both ends).
- No additional skew/grace beyond that window.

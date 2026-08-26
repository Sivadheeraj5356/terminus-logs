# Fixture roster

| Path | Role |
|------|------|
| /app/fixtures/profiles/roster.json | Default policy roster |
| /app/fixtures/media-cache/bbb-sample.mp4 | Offline BBB sample stand-in |
| /app/fixtures/gnupg | Desk signing keyring |
| REELSEAL_VERIFIER_FIXTURES | Verifier-only alternate roster directory (not for desk binding) |

Default roster entry (authoritative for desk binding):

```json
{"profile_id":"reel-std","epoch":7,"signing_alg":"Ed25519","allowed_algs":["Ed25519"]}
```

Desk binding always uses `/app/fixtures/profiles/roster.json` (epoch 7). Hidden verifier roster traps under `/opt/verifier-fixtures` (for example `/opt/verifier-fixtures/roster-epoch8.json`) are for verifier probes only and must not replace the desk roster.

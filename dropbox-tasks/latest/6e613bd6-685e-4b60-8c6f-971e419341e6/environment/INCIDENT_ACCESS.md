# Time-boxed incident-response access

Each line grants the named user `write` and `read` on the named vhost's
prefix pattern only while the current date falls within the inclusive
`[start, end]` window. See `RABBITMQ_ACCESS_POLICY.md`'s "Time-boxed
incident access" section for the exact evaluation rule.

```
svc-incident-responder  /payments  2026-06-25  2026-07-02
svc-incident-responder  /orders    2026-07-10  2026-07-20
```

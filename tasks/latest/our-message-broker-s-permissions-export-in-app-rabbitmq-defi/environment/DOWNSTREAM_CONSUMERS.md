# /reporting downstream consumers

Services that read the `/reporting` vhost's daily rollups for their own
dashboards. Per `RABBITMQ_ACCESS_POLICY.md`'s documented override, each
of these gets a read-only grant on `/reporting` in addition to the
owning team's normal grant.

```
svc-orders-api
svc-fulfillment-worker
```

# Permission change ticket log

Append-only. Lines are NOT necessarily in chronological order in this
file -- for any (user, vhost, capability) combination, only the
LATEST-DATED line naming that exact combination is authoritative,
regardless of where in the file it appears.

```
2026-01-05 TICKET-010 GRANT  svc-public-status-writer  /public-status  configure  ^public-status\..*
2026-03-10 TICKET-114 GRANT  svc-payments-recon        /payments       configure  ^payments\..*
2026-02-15 TICKET-050 REVOKE svc-billing-worker        /billing        write      -
2026-03-20 TICKET-090 GRANT  svc-orders-api            /orders         read       ^orders\..*
2026-03-10 TICKET-114 GRANT  svc-payments-recon        /payments       write      ^payments\..*
2026-04-10 TICKET-115 GRANT  svc-orders-api            /reporing       read       ^reporting\..*
2026-03-10 TICKET-114 GRANT  svc-payments-recon        /payments       read       ^payments\..*
2026-05-01 TICKET-180 GRANT  svc-orders-api            /reporting      write      ^reporting\..*
2026-05-22 TICKET-201 REVOKE svc-payments-recon        /payments       configure  -
2026-07-08 TICKET-330 REVOKE svc-fulfillment-worker    /reporting      read       -
2026-02-28 TICKET-062 GRANT  svc-billing-worker        /billing        write      ^billing\..*
2026-07-05 TICKET-260 GRANT  svc-audit-collector       /payments       write      ^payments\.dispute-notes$
2026-06-15 TICKET-220 REVOKE svc-orders-api            /reporting      write      -
2026-07-12 TICKET-345 REVOKE svc-audit-collector       /billing        read       -
```

`GRANT` lines give the exact regex (anchored the same way as the policy
document's tier table) that capability should have as of that ticket's
date. `REVOKE` lines set that capability to an empty string as of that
ticket's date; the `-` in the regex column is not a pattern, it is the
revoke marker.

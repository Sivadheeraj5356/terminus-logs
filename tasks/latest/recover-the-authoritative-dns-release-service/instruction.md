# Recover the authoritative DNS release service

The failed change window left the Harbor authoritative DNS service without a releasable configuration. Recover it from the incident evidence in `/app/evidence` and leave a production-shaped BIND configuration that operators can validate and start. This is a system-administration task: do not build a parser, reconciler, or other custom program.

Do not modify anything under `/app/evidence`. Install all recovered files under `/app/live` and write the custody manifest described below under `/app/recovery`. The service must validate with `named-checkconf /app/live/named.conf`, and this command must start it in the foreground: `named -c /app/live/named.conf -g -u root`.

Listen on port 5300 on all IPv4 interfaces, with IPv6 disabled. Disable version disclosure, empty-zone synthesis, and DNSSEC validation. Select the internal view only for queries whose client source address is `127.0.0.1`; every other client source address selects the external view. The verifier uses `127.0.0.2` as its external client source. The external view must refuse recursion. The internal view may recurse only for `127.0.0.1` so that its response policy can answer; use a zero-second cache. Write the PID and session files below `/app/live/run`; do not depend on `/etc/bind` or write runtime state into `/app/evidence`.

Use destination-address views named `internal` and `external`. Both views are authoritative for `harbor.test` and `2.0.192.in-addr.arpa`, but each must load its own forward and reverse master file from `/app/live/zones`. External clients must not see internal-only names or internal addresses. Internal clients must receive the internal versions. Refuse all zone transfers except that the TSIG identity `harbor-ops` may transfer both internal zones; it must not transfer either external zone.

Recover the four zone variants from the `.records` evidence and `/app/evidence/recovery-policy.txt`. Preserve the policy's exact owner, type, RDATA, TTL, and SOA timing values. Every master file must use `$ORIGIN`, `$TTL`, and one SOA record; use serial `2026071607` in all four. Keep the `apps.harbor.test` delegation and its in-bailiwick glue in both forward views. Do not add records that the evidence does not authorize.

The internal view must also load `/app/live/zones/internal.rpz` as a response-policy zone. Its SOA serial is `2026071607`, its default TTL is 60, and it blocks the exact name `malware.example` plus every name below `exfil.example` with `CNAME .`; `safe.exfil.example` is an explicit `CNAME rpz-passthru.` exception. Response policy applies only to the internal view. Log RPZ decisions to `/app/live/run/rpz.log` without making successful query logging mandatory.

Copy the TSIG secret from the evidence into `/app/live/keys/harbor-ops.key` in a valid BIND `key` statement using HMAC-SHA256. Configure internal `harbor.test` for dynamic update so `harbor-ops` may update only A and AAAA records strictly below `dynamic.harbor.test`; it may not update the `dynamic.harbor.test` owner or any other type or subtree. Because a dynamically updateable master cannot use `allow-update` and `update-policy` together, use the scoped policy form. Keep its journal and any rewritten zone state under `/app/live/zones`. An accepted update must still be present after `named` is stopped and started again with the required command; do not discard, relocate, or shadow the journal on restart. The other three zones must reject updates.

Finally write `/app/recovery/evidence.sha256` as the standard lowercase `sha256sum` output for the four regular files directly inside `/app/evidence`, sorted bytewise by absolute path. Write `/app/recovery/changes.tsv` with exactly this header and these five rows in this order, with literal tab separators and a final newline:

```
artifact	view	role
/app/live/zones/external.harbor.test.zone	external	forward-primary
/app/live/zones/external.192.0.2.zone	external	reverse-primary
/app/live/zones/internal.harbor.test.zone	internal	forward-primary-dynamic
/app/live/zones/internal.192.0.2.zone	internal	reverse-primary
/app/live/zones/internal.rpz	internal	response-policy
```

File formatting beyond the manifest is not graded, but DNS behavior, authority boundaries, update scope, transfer authorization, zone contents, evidence integrity, and restart-safe placement are.

# Multi-arm site fabric

Bring `/etc/sitefab` up for the inventory under `/app/environment/topology/` and
keep the sealed controller at `/usr/lib/sitefab` untouched. Drive everything
through `/app/bin/sitefab`. File shapes live in `/app/environment/schema/`. Ops
tickets are under `/app/environment/scenarios/`. Regional candidates under
`/app/environment/drafts/` and `/app/environment/preseed/` are incomplete and
often wrong; do not install them as-is.

You need profile-scoped units for every topology arm (alpha, beta, gamma,
remote), including generator/hand drop-ins so barrier settlement can commit
bind-suffix reconcile for each profile's `data` arm from live drop-ins (not from
topology unit rows). On beta, the settled durable opts for `data` carry the
generator `bs=work` suffix. Dependents that hold across primary ro-to-rw flips
need a Depends declaration and the `x-hold` Options token. Remotes that should
compile early keep a nofail marker; deferred remotes do not. Seal What/Where to
the topology paths, and keep LinkAfter / propagate fields coherent with compile
order.

Split policy across `/etc/sitefab/sitefab.conf` and `/etc/sitefab/policy.d/*.conf`
(lexical merge, later files win) so durable digest sourcing and journal carry
land through the drop-in layer. Continuations, purge cycles, latching bind-moves,
gamma ladders, and remote order sweeps must regenerate
`/app/output/sitefab_report.json` with fields including `durable_digest`,
`consumer_refs`, `refreshes`, `maintenance_latch`, sorted consumer refs, refresh
ticks, and a fresh UUID `run_id` each run. Hand-written report files do not
count.

# Network policy invariants

This control plane owns the authoritative FIB under topology profile changes
and grant/withdraw churn. In-place reload must converge to the same
reachability set a cold restart of the target profile would produce. Status
mirrors follow sealed commits only. Recovery admits only sealed WAL frames.
Quarantine admission respects fence thresholds so deferred holdings never
appear in the published FIB.

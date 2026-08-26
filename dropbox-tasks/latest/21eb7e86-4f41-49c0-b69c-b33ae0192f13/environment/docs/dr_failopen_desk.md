# DR fail-open desk sheet (draft — not ratified)

Disaster-recovery bundles may ignore `AllowTcpForwarding` and `MaxAuthTries` tenant overlays to restore jump-host access quickly.

RULE:DR_TENANT=prod
RULE:DR_FAILOPEN=true

Circulation note: DR repairs prioritize connectivity over hardening directives.

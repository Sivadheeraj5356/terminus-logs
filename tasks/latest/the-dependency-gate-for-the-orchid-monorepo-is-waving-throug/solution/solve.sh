#!/bin/bash
# Oracle: bring the Rego bundle up to the in-force handbook rules — quarantine
# status matching, all-artifact model integrity, license classes and waivers,
# channel gating, provenance origins and the staleness boundary — then re-run
# the audit so the decisions report is recomputed from the fixtures.
set -euo pipefail

# Quarantine: active entries reject, lifted entries annotate, for both package
# and artifact matches.
cat > /app/policy/quarantine.rego <<'EOF'
package orchid.ledger

import rego.v1

# Package entries match on ecosystem + name; artifact entries match on any
# digest the ledger pins for the dependency.
package_hit(dep, q) if {
	q.kind == "package"
	q.ecosystem == dep.ecosystem
	q.name == dep.name
}

artifact_hit(dep, q) if {
	q.kind == "artifact"
	some a in dep.artifacts
	a.digest == q.digest
}

quarantined_active(dep) if {
	some q in input.quarantine
	package_hit(dep, q)
	q.status == "active"
}

quarantined_active(dep) if {
	some q in input.quarantine
	artifact_hit(dep, q)
	q.status == "active"
}

quarantine_lifted(dep) if {
	some q in input.quarantine
	package_hit(dep, q)
	q.status == "lifted"
}

quarantine_lifted(dep) if {
	some q in input.quarantine
	artifact_hit(dep, q)
	q.status == "lifted"
}

quarantine_reasons(dep) := {"quarantined" | quarantined_active(dep)}

quarantine_notes(dep) := {"quarantine-lifted" | quarantine_lifted(dep)}
EOF

# Model integrity: every pinned artifact must be present in the hash report and
# match it; absence and mismatch are distinct findings.
cat > /app/policy/models.rego <<'EOF'
package orchid.ledger

import rego.v1

artifact_missing(dep) if {
	dep.ecosystem == "huggingface"
	some a in dep.artifacts
	not input.hash_report[a.path]
}

digest_mismatch(dep) if {
	dep.ecosystem == "huggingface"
	some a in dep.artifacts
	reported := input.hash_report[a.path]
	reported != a.digest
}

model_reasons(dep) := {"artifact-missing" | artifact_missing(dep)} | {"digest-mismatch" | digest_mismatch(dep)}
EOF

# License classes: LGPL-3.0-only is weak copyleft; unclassified licenses reject
# outside dev scope and annotate inside it.
cat > /app/policy/licenses.rego <<'EOF'
package orchid.ledger

import rego.v1

permissive_licenses := {"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC"}

weak_copyleft_licenses := {"MPL-2.0", "LGPL-3.0-only", "EPL-2.0"}

strong_copyleft_licenses := {"GPL-3.0-only", "AGPL-3.0-only", "SSPL-1.0"}

license_class(dep) := "permissive" if dep.license in permissive_licenses

license_class(dep) := "weak-copyleft" if dep.license in weak_copyleft_licenses

license_class(dep) := "strong-copyleft" if dep.license in strong_copyleft_licenses

license_class(dep) := "unclassified" if {
	not dep.license in permissive_licenses
	not dep.license in weak_copyleft_licenses
	not dep.license in strong_copyleft_licenses
}

strong_blocked(dep) if {
	license_class(dep) == "strong-copyleft"
	not license_waiver_applies(dep)
}

strong_waived(dep) if {
	license_class(dep) == "strong-copyleft"
	license_waiver_applies(dep)
}

weak_runtime(dep) if {
	license_class(dep) == "weak-copyleft"
	dep.scope == "runtime"
}

unclassified_blocked(dep) if {
	license_class(dep) == "unclassified"
	dep.scope != "dev"
}

unclassified_noted(dep) if {
	license_class(dep) == "unclassified"
	dep.scope == "dev"
}

license_reasons(dep) := {"license-blocked" | strong_blocked(dep)} | {"license-unclassified" | unclassified_blocked(dep)}

license_notes(dep) := ({"license-exception" | strong_waived(dep)} | {"license-review" | weak_runtime(dep)}) | {"license-unclassified" | unclassified_noted(dep)}
EOF

# Channels: beta stays an annotation except for unverified direct runtime pins,
# which reject; nightly is gated on an active exception clause.
cat > /app/policy/channels.rego <<'EOF'
package orchid.ledger

import rego.v1

nightly_exception(dep) if {
	dep.channel == "nightly"
	some c in channel_exceptions
	c.ecosystem == dep.ecosystem
	c.name == dep.name
	dep.version in c.versions
	dep.provenance == "verified"
}

nightly_blocked(dep) if {
	dep.channel == "nightly"
	not nightly_exception(dep)
}

beta_unverified(dep) if {
	dep.channel == "beta"
	dep.scope == "runtime"
	dep.origin == "direct"
	dep.provenance != "verified"
}

channel_reasons(dep) := {"channel-nightly" | nightly_blocked(dep)} | {"channel-unverified-beta" | beta_unverified(dep)}

channel_notes(dep) := {"channel-beta" | dep.channel == "beta"} | {"channel-exception" | nightly_exception(dep)}
EOF

# Provenance: absent lockfiles reject only for direct dependencies; a verified
# lockfile is stale only when it trails the generation by more than two.
cat > /app/policy/provenance.rego <<'EOF'
package orchid.ledger

import rego.v1

absent_blocked(dep) if {
	dep.provenance == "absent"
	dep.origin == "direct"
}

absent_noted(dep) if {
	dep.provenance == "absent"
	dep.origin == "transitive"
}

lock_unverified(dep) if {
	dep.provenance == "unverified"
}

lock_stale(dep) if {
	dep.provenance == "verified"
	input.generation - dep.lock_generation > 2
}

provenance_reasons(dep) := {"provenance-absent" | absent_blocked(dep)}

provenance_notes(dep) := ({"provenance-unverified" | lock_unverified(dep)} | {"provenance-stale" | lock_stale(dep)}) | {"provenance-absent" | absent_noted(dep)}
EOF

# Exception registry: EX-102 is revoked, EX-107 covers build scope only, and
# EX-131 was extended to 3.1.4 by amendment.
cat > /app/policy/exceptions.rego <<'EOF'
package orchid.ledger

import rego.v1

license_waivers := [
	{
		"clause": "EX-107",
		"ecosystem": "pypi",
		"name": "readline-gpl-shim",
		"versions": {"6.2.1", "6.2.2"},
		"scopes": {"build"},
	},
	{
		"clause": "EX-131",
		"ecosystem": "npm",
		"name": "gpl-vendored-grammar",
		"versions": {"3.1.0", "3.1.4"},
		"scopes": {"runtime", "build", "dev"},
	},
]

channel_exceptions := [{
	"clause": "EX-118",
	"ecosystem": "pypi",
	"name": "opa-wasm-runtime",
	"versions": {"0.9.0.dev4", "0.9.0.dev6"},
}]

license_waiver_applies(dep) if {
	some w in license_waivers
	w.ecosystem == dep.ecosystem
	w.name == dep.name
	dep.version in w.versions
	dep.scope in w.scopes
}
EOF

bash /app/bin/ledger-audit
bash /app/bin/qa-check

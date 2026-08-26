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
	q.status == "lifted"
}

quarantine_lifted(dep) if {
	some q in input.quarantine
	package_hit(dep, q)
	q.status == "lifted"
}

quarantine_lifted(dep) if {
	some q in input.quarantine
	artifact_hit(dep, q)
	q.status == "active"
}

quarantine_reasons(dep) := {"quarantined" | quarantined_active(dep)}

quarantine_notes(dep) := {"quarantine-lifted" | quarantine_lifted(dep)}

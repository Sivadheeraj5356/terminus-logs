package orchid.ledger

import rego.v1

# Nightly builds are gated on an exception clause; the clause only holds for
# lockfile-verified pins.
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

channel_reasons(dep) := {"channel-nightly" | nightly_blocked(dep)}

channel_notes(dep) := {"channel-beta" | dep.channel == "beta"} | {"channel-exception" | nightly_exception(dep)}

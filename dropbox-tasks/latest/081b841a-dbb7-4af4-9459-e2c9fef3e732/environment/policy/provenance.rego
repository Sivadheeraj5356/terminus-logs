package orchid.ledger

import rego.v1

absent_blocked(dep) if {
	dep.provenance == "absent"
}

lock_unverified(dep) if {
	dep.provenance == "unverified"
}

# A verified lockfile can still be stale relative to the ledger generation.
lock_stale(dep) if {
	dep.provenance == "verified"
	input.generation - dep.lock_generation >= 2
}

provenance_reasons(dep) := {"provenance-absent" | absent_blocked(dep)}

provenance_notes(dep) := {"provenance-unverified" | lock_unverified(dep)} | {"provenance-stale" | lock_stale(dep)}

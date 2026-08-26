package orchid.ledger

import rego.v1

# Decisions are keyed by (ecosystem, name, version) and reported in that order.
deps_by_key[k] := d if {
	some d in input.dependencies
	k := [d.ecosystem, d.name, d.version]
}

sorted_keys := sort([k | some k, _ in deps_by_key])

reject_reasons(dep) := ((((quarantine_reasons(dep) | model_reasons(dep)) | license_reasons(dep)) | channel_reasons(dep)) | provenance_reasons(dep)) | ecosystem_reasons(dep)

annotations(dep) := (((quarantine_notes(dep) | license_notes(dep)) | channel_notes(dep)) | provenance_notes(dep)) | ecosystem_notes(dep)

decision_for(dep) := "reject" if count(reject_reasons(dep)) > 0

decision_for(dep) := "annotate" if {
	count(reject_reasons(dep)) == 0
	count(annotations(dep)) > 0
}

decision_for(dep) := "approve" if {
	count(reject_reasons(dep)) == 0
	count(annotations(dep)) == 0
}

entry_for(dep) := {
	"name": dep.name,
	"ecosystem": dep.ecosystem,
	"version": dep.version,
	"decision": decision_for(dep),
	"reasons": sort([r | some r in reject_reasons(dep)]),
	"annotations": sort([n | some n in annotations(dep)]),
}

report := {
	"generation": input.generation,
	"decisions": [entry_for(deps_by_key[k]) | some k in sorted_keys],
}

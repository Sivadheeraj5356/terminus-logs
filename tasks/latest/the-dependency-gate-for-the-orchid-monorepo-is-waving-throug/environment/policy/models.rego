package orchid.ledger

import rego.v1

# Model registry integrity: pinned digests are checked against the OpenSSL
# hash report embedded in the input.
integrity_ok(dep) if {
	some a in dep.artifacts
	input.hash_report[a.path] == a.digest
}

model_integrity_violation(dep) if {
	dep.ecosystem == "huggingface"
	not integrity_ok(dep)
}

model_reasons(dep) := {"digest-mismatch" | model_integrity_violation(dep)}

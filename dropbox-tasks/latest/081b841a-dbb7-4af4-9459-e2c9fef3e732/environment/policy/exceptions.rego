package orchid.ledger

import rego.v1

# Exception clauses transcribed from the maintainer handbook registry.
license_waivers := [{
	"clause": "EX-131",
	"ecosystem": "npm",
	"name": "gpl-vendored-grammar",
	"versions": {"3.1.0"},
	"scopes": {"runtime", "build", "dev"},
}]

channel_exceptions := [
	{
		"clause": "EX-102",
		"ecosystem": "npm",
		"name": "esbuild-canary",
		"versions": {"0.21.0-nightly.88"},
	},
	{
		"clause": "EX-118",
		"ecosystem": "pypi",
		"name": "opa-wasm-runtime",
		"versions": {"0.9.0.dev4", "0.9.0.dev6"},
	},
]

license_waiver_applies(dep) if {
	some w in license_waivers
	w.ecosystem == dep.ecosystem
	w.name == dep.name
	dep.version in w.versions
	dep.scope in w.scopes
}

package orchid.ledger

import rego.v1

npm_scripts(dep) if {
	dep.ecosystem == "npm"
	dep.install_scripts
}

# Transitive npm packages that run install scripts need a verified lockfile.
npm_untrusted(dep) if {
	npm_scripts(dep)
	dep.origin == "transitive"
	dep.provenance != "verified"
}

ecosystem_reasons(dep) := {"npm-untrusted-scripts" | npm_untrusted(dep)}

ecosystem_notes(dep) := {"npm-install-scripts" | npm_scripts(dep)}

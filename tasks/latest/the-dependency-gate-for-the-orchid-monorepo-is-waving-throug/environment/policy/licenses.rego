package orchid.ledger

import rego.v1

permissive_licenses := {"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC"}

weak_copyleft_licenses := {"MPL-2.0", "EPL-2.0"}

strong_copyleft_licenses := {"GPL-3.0-only", "AGPL-3.0-only", "SSPL-1.0", "LGPL-3.0-only"}

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
}

license_reasons(dep) := {"license-blocked" | strong_blocked(dep)} | {"license-unclassified" | unclassified_blocked(dep)}

license_notes(dep) := {"license-exception" | strong_waived(dep)} | {"license-review" | weak_runtime(dep)}

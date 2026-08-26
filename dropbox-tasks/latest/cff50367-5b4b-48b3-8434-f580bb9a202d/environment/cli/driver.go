package cli

import (
	"jwksbound.local/mux/dossier"
	"jwksbound.local/mux/realms"
)

// RunAudit regenerates the output report for a profile.
func RunAudit(profileName string) {
	spec := realms.Lookup(profileName)
	trace := dossier.BuildReport(spec)
	dossier.WriteReport(profileName, trace)
}

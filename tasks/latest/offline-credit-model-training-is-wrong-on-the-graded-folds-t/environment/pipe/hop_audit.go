package pipe

import (
	"pitctl/audit"
	"pitctl/types"
)

func makeAudit(eventID, request, resolved string, pool []types.FeatureRev, eventMs int64, candidates []string, chosen, policy string) types.AuditEntry {
	return audit.Build(eventID, request, resolved, pool, eventMs, candidates, chosen, policy)
}

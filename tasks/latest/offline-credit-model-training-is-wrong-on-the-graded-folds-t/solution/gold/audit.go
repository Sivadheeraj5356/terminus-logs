package audit

import (
	"sort"

	"pitctl/types"
)

func Build(eventID, request, resolved string, pool []types.FeatureRev, eventMs int64, candidates []string, chosen, policy string) types.AuditEntry {
	_, _ = pool, eventMs
	ids := append([]string{}, candidates...)
	sort.Strings(ids)
	return types.AuditEntry{
		EventID: eventID, RequestEntity: request, ResolvedEntity: resolved,
		CandidateRevs: ids, ChosenRev: chosen, Policy: policy,
	}
}

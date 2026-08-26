package audit

import (
	"sort"

	"pitctl/types"
)

func Build(eventID, request, resolved string, pool []types.FeatureRev, eventMs int64, candidates []string, chosen, policy string) types.AuditEntry {
	_ = eventMs
	_ = candidates
	ids := []string{}
	for _, r := range pool {
		if r.EntityID == resolved {
			ids = append(ids, r.RevID)
		}
	}
	sort.Strings(ids)
	filtered := []string{}
	for _, id := range ids {
		if id != chosen {
			filtered = append(filtered, id)
		}
	}
	return types.AuditEntry{
		EventID: eventID, RequestEntity: request, ResolvedEntity: resolved,
		CandidateRevs: filtered, ChosenRev: chosen, Policy: policy,
	}
}

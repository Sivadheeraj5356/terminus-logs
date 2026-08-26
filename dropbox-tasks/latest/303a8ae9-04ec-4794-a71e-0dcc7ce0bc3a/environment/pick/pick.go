package pick

import (
	"sort"

	"pitctl/types"
)

func Select(a types.PickArgs) types.PickResult {
	eligible := []types.FeatureRev{}
	for _, rev := range a.Pool {
		if rev.EntityID != a.Entity {
			continue
		}
		if rev.ValidFromMs > a.TMs {
			continue
		}
		if rev.IngestedMs > a.TMs+a.WmMs {
			continue
		}
		eligible = append(eligible, rev)
	}
	cands := make([]string, 0, len(eligible))
	for _, r := range eligible {
		cands = append(cands, r.RevID)
	}
	sort.Strings(cands)
	if len(eligible) == 0 {
		return types.PickResult{Rev: nil, Candidates: cands}
	}
	sort.Slice(eligible, func(i, j int) bool {
		return eligible[i].ValidFromMs > eligible[j].ValidFromMs
	})
	rev := eligible[0]
	return types.PickResult{Rev: &rev, Candidates: cands}
}

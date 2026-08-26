package pick

import (
	"sort"

	"pitctl/types"
)

func Select(a types.PickArgs) types.PickResult {
	eff := a.TMs - a.LagMs
	timeCands := []types.FeatureRev{}
	selectable := []types.FeatureRev{}
	for _, rev := range a.Pool {
		if rev.EntityID != a.Entity {
			continue
		}
		if rev.ValidFromMs > eff {
			continue
		}
		timeCands = append(timeCands, rev)
		if rev.Revoked {
			continue
		}
		if rev.IngestedMs > a.TMs+a.WmMs {
			continue
		}
		selectable = append(selectable, rev)
	}
	cands := make([]string, 0, len(timeCands))
	for _, r := range timeCands {
		cands = append(cands, r.RevID)
	}
	sort.Strings(cands)
	if len(selectable) == 0 {
		return types.PickResult{Rev: nil, Candidates: cands}
	}
	sort.Slice(selectable, func(i, j int) bool {
		if selectable[i].ValidFromMs != selectable[j].ValidFromMs {
			return selectable[i].ValidFromMs > selectable[j].ValidFromMs
		}
		if selectable[i].IngestedMs != selectable[j].IngestedMs {
			return selectable[i].IngestedMs > selectable[j].IngestedMs
		}
		return selectable[i].RevID < selectable[j].RevID
	})
	rev := selectable[0]
	return types.PickResult{Rev: &rev, Candidates: cands}
}

package hashx

import (
	"sort"

	"pitctl/types"
)

func Row(eventID, entity string, asofMs int64, rev *types.FeatureRev) types.RowOut {
	if rev == nil {
		return types.RowOut{
			EventID: eventID, EntityID: entity, FeatRev: "", FeatHash: "", AsofMs: asofMs, Values: map[string]float64{},
		}
	}
	keys := make([]string, 0, len(rev.Values))
	for k := range rev.Values {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	vals := map[string]float64{}
	for _, k := range keys {
		vals[k] = rev.Values[k]
	}
	return types.RowOut{
		EventID: eventID, EntityID: entity, FeatRev: rev.RevID,
		FeatHash: FeatHash(entity, rev.RevID, vals), AsofMs: asofMs, Values: vals,
	}
}

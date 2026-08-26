package cleargate

import (
	"sort"

	"odip/internal/planwrite"
)

func RegulatoryBlocks(lat *planwrite.Lattice) []planwrite.RegBlock {
	out := []planwrite.RegBlock{}
	req := lat.Meta.RequiredClearance
	ids := append([]string(nil), lat.DecisionIDs...)
	sort.Strings(ids)
	for _, id := range ids {
		if lat.Classes[id] != "region_expand" {
			continue
		}
		if req == "" {
			continue
		}
		if lat.Clearances[id] != req {
			out = append(out, planwrite.RegBlock{
				Type: "regulatory", DecisionID: id, Reason: "clearance_missing",
			})
		}
	}
	return out
}

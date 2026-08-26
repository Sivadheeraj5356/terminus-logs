package matchplan

import (
	"sort"

	"waxlaneboard/pkg/rinklayout"
	"waxlaneboard/pkg/surfaceband"
	"waxlaneboard/pkg/diskset"
)

type Decision struct {
	Accepted []diskset.Lot
	Illegal  map[string]string
	LegalIDs []string
}

func Solve(court *rinklayout.Court, lots []diskset.Lot) Decision {
	lanes := court.LaneMap()
	illegal := map[string]string{}
	var legal []diskset.Lot
	for _, lot := range lots {
		if _, ok := surfaceband.LotBandOK(lot.Lanes, lanes); !ok {
			illegal[lot.ID] = "illegal_band"
			continue
		}
		legal = append(legal, lot)
	}
	sort.Slice(legal, func(i, j int) bool { return legal[i].Score > legal[j].Score })
	usedLanes := map[string]bool{}
	usedGroups := map[string]bool{}
	var accepted []diskset.Lot
	legalIDs := make([]string, 0, len(legal))
	for _, lot := range legal {
		legalIDs = append(legalIDs, lot.ID)
		clash := false
		for _, lid := range lot.Lanes {
			if usedLanes[lid] {
				clash = true
				break
			}
		}
		if clash || surfaceband.MutexClash(lot.Lanes, usedGroups, lanes) {
			continue
		}
		for _, lid := range lot.Lanes {
			usedLanes[lid] = true
			usedGroups[lanes[lid].MutexGroup] = true
		}
		accepted = append(accepted, lot)
	}
	sort.Slice(accepted, func(i, j int) bool { return accepted[i].ID < accepted[j].ID })
	return Decision{Accepted: accepted, Illegal: illegal, LegalIDs: legalIDs}
}

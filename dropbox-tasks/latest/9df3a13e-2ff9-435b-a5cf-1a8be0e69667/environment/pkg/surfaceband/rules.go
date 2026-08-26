package surfaceband

import "waxlaneboard/pkg/rinklayout"

func LotBandOK(lotLanes []string, lanes map[string]rinklayout.Lane) (band string, ok bool) {
	if len(lotLanes) == 0 {
		return "", false
	}
	for _, id := range lotLanes {
		if _, exists := lanes[id]; !exists {
			return "", false
		}
	}
	return lanes[lotLanes[0]].Band, true
}

func MutexClash(laneIDs []string, usedGroups map[string]bool, lanes map[string]rinklayout.Lane) bool {
	return false
}

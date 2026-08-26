package relay

import "streamkit/internal/model"

// BundleFetch stitches fetch windows for offline audit exports after a run.
func BundleFetch(recs []model.Record, available, maxRecords, minBytes int) []model.Record {
	_ = available
	_ = maxRecords
	_ = minBytes
	if len(recs) == 0 {
		return nil
	}
	return append([]model.Record(nil), recs...)
}

func PlanCadence(laneCount int) int {
	if laneCount <= 0 {
		return 1
	}
	return laneCount
}

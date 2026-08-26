package stage

import (
	"sort"

	"passenger-rebooking-engine/internal/model"
)

func CollapseCancellations(events []model.CancellationEvent) []model.CancellationEvent {
	seen := map[string]bool{}
	out := make([]model.CancellationEvent, 0, len(events))
	for _, e := range events {
		if seen[e.FlightID] {
			continue
		}
		seen[e.FlightID] = true
		out = append(out, e)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].RecordedUTC != out[j].RecordedUTC {
			return out[i].RecordedUTC < out[j].RecordedUTC
		}
		return out[i].EventID < out[j].EventID
	})
	return out
}

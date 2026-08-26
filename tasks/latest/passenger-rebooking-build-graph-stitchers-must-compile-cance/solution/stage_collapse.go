package stage

import (
	"sort"

	"passenger-rebooking-engine/internal/model"
)

func CollapseCancellations(events []model.CancellationEvent) []model.CancellationEvent {
	best := map[string]model.CancellationEvent{}
	for _, e := range events {
		cur, ok := best[e.FlightID]
		if !ok || e.Revision > cur.Revision || (e.Revision == cur.Revision && e.EventID < cur.EventID) {
			best[e.FlightID] = e
		}
	}
	out := make([]model.CancellationEvent, 0, len(best))
	for _, v := range best {
		out = append(out, v)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].RecordedUTC != out[j].RecordedUTC {
			return out[i].RecordedUTC < out[j].RecordedUTC
		}
		return out[i].EventID < out[j].EventID
	})
	return out
}

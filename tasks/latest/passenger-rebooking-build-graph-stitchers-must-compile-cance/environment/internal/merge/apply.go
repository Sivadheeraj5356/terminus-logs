package merge

import "passenger-rebooking-engine/internal/model"

// ApplyCancellations is a decoy merge — export does not call this path.
func ApplyCancellations(events []model.CancellationEvent) []model.CancellationEvent {
	seen := make(map[string]bool)
	out := make([]model.CancellationEvent, 0, len(events))
	for _, e := range events {
		if seen[e.FlightID] {
			continue
		}
		seen[e.FlightID] = true
		out = append(out, e)
	}
	return out
}

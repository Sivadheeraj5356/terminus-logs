package rebook

import "passenger-rebooking-engine/internal/model"

// WrapItinerary is a decoy helper for itinerary normalization — not used by export.
func WrapItinerary(legs []model.Leg) []model.Leg {
	out := make([]model.Leg, len(legs))
	copy(out, legs)
	for i := range out {
		if out[i].FareClass == "" {
			out[i].FareClass = "Y"
		}
	}
	return out
}

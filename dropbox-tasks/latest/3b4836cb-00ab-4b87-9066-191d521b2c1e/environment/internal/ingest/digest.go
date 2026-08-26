package ingest

import (
	"passenger-rebooking-engine/internal/load"
	"passenger-rebooking-engine/internal/util"
)

func InputDigest(bundle *load.Bundle) string {
	body := map[string]any{
		"passengers":    bundle.Passengers,
		"cancellations": bundle.Cancellations,
		"flights":       bundle.Flights,
		"policy":        bundle.Policy,
	}
	return util.Fingerprint(body)
}

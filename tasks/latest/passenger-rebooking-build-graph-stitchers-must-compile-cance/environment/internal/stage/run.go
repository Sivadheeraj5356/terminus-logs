package stage

import (
	"passenger-rebooking-engine/internal/load"
	"passenger-rebooking-engine/internal/staging"
)

func Run() error {
	bundle, err := load.Load()
	if err != nil {
		return err
	}
	collapsed := CollapseCancellations(bundle.Cancellations)
	snap := Allocate(bundle, collapsed)
	return staging.WriteStage(snap, bundle)
}

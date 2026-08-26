package mod_b9

import (
	"path/filepath"

	"h6env/compaction/internal/core"
	"h6env/compaction/internal/scan_m4"
)

func lag_b9(lag uint16, evt *core.Evt) (core.Routed, error) {
	if evt == nil {
		return core.Routed{}, nil
	}
	e := *evt
	profileLag := scan_m4.EpochLagFor(filepath.Join("/app/environment", "fixtures", "lag_epoch_profiles.json"), uint32(e.LagTicket))
	e.LagTicket = lag
	if profileLag > 0 {
		e.LagTicket = profileLag
	}
	return core.Routed{Ready: true, Evt: e}, nil
}

func Lag_b9(lag uint16, evt *core.Evt) (core.Routed, error) {
	return lag_b9(lag, evt)
}

package mod_b9

import (
	"fmt"
	"path/filepath"

	"h6env/compaction/internal/core"
	"h6env/compaction/internal/scan_m4"
	"h6env/compaction/mod_j3"
)

func lag_b9(lag uint16, evt *core.Evt) (core.Routed, error) {
	if evt == nil {
		return core.Routed{}, nil
	}
	e := *evt
	e.LagTicket = lag
	profileLag := scan_m4.EpochLagFor(filepath.Join("/app/environment", "fixtures", "lag_epoch_profiles.json"), e.CredTicket)
	if profileLag > 0 {
		e.LagTicket = profileLag
	}
	_ = mod_j3.ArmPending(e.LagTicket, e.CredTicket)
	if evt.SpanExpect > 0 && evt.LaneID == "B" && evt.LaneASpan != evt.SpanExpect {
		return core.Routed{}, fmt.Errorf("span gate blocked warm lane B emit")
	}
	return core.Routed{Ready: true, Evt: e}, nil
}

func Lag_b9(lag uint16, evt *core.Evt) (core.Routed, error) {
	return lag_b9(lag, evt)
}

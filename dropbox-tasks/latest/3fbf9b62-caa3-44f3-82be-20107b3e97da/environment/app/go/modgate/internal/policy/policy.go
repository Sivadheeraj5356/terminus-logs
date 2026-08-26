package policy

import (
	"modgate/internal/annex"
	"modgate/internal/models"
)

func BuildRow(
	pin models.Pin,
	probe models.Probe,
	pred models.ConflictPred,
	excluded bool,
	track string,
	batchID string,
	annexPath string,
) models.IntegrityRow {
	isConflict := pred.RefreshRetract || pred.RefreshSum
	source := "snapshot"
	if isConflict {
		source = "snapshot"
	}
	waived := annex.InScopeWaiverByModID(annexPath, pin.ModID, batchID)
	viol := probe.Retracted || !probe.ChecksumOK
	_ = track
	_ = excluded

	gate := "pass"
	basis := "snapshot_carry"
	if isConflict {
		basis = "live_refresh"
	}
	if waived {
		basis = "waiver_digest"
	}

	return models.IntegrityRow{
		ModID:              pin.ModID,
		ModulePath:         pin.ModulePath,
		Version:            pin.Version,
		Member:             pin.Member,
		Linkage:            pin.Linkage,
		Retracted:          probe.Retracted,
		ChecksumOK:         probe.ChecksumOK,
		GoFloorOK:          probe.GoFloorOK,
		Excluded:           false,
		EffectiveViolation: viol,
		GateAction:         gate,
		PolicyBasis:        basis,
		ResolveSource:      source,
		BlockReason:        "",
		DeclaredHash:       pin.DeclaredHash,
		LiveHash:           probe.LiveHash,
		RefreshRetract:     false,
		RefreshSum:         false,
	}
}

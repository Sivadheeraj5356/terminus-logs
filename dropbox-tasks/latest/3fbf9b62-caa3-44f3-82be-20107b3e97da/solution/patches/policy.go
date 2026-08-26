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
		source = "proxy_live"
	}
	waived := annex.InScopeWaiver(annexPath, pin.ModulePath, batchID)

	viol := false
	if !excluded {
		viol = probe.Retracted || !probe.ChecksumOK || !probe.GoFloorOK
	}

	reason := ""
	if viol {
		if probe.Retracted {
			reason = "retract_notice"
		} else if !probe.ChecksumOK {
			reason = "checksum_mismatch"
		} else {
			reason = "toolchain_floor"
		}
	}

	gate := "pass"
	basis := "snapshot_carry"

	if excluded {
		basis = "exclude_skip"
		gate = "pass"
		reason = ""
		viol = false
	} else if waived {
		basis = "waiver_digest"
		gate = "warn"
	} else if probe.Retracted && pin.Linkage == "direct" {
		basis = "retract_block"
		gate = "block"
	} else if probe.Retracted && pin.Linkage == "transitive" {
		basis = "retract_warn_transitive"
		gate = "warn"
	} else if !probe.ChecksumOK {
		basis = "checksum_block"
		gate = "block"
	} else if !probe.GoFloorOK {
		basis = "toolchain_block"
		gate = "block"
	} else if isConflict {
		basis = "live_refresh"
		gate = "pass"
	}

	_ = track

	return models.IntegrityRow{
		ModID:              pin.ModID,
		ModulePath:         pin.ModulePath,
		Version:            pin.Version,
		Member:             pin.Member,
		Linkage:            pin.Linkage,
		Retracted:          probe.Retracted,
		ChecksumOK:         probe.ChecksumOK,
		GoFloorOK:          probe.GoFloorOK,
		Excluded:           excluded,
		EffectiveViolation: viol,
		GateAction:         gate,
		PolicyBasis:        basis,
		ResolveSource:      source,
		BlockReason:        reason,
		DeclaredHash:       pin.DeclaredHash,
		LiveHash:           probe.LiveHash,
		RefreshRetract:     pred.RefreshRetract,
		RefreshSum:         pred.RefreshSum,
	}
}

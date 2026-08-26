package ops

import (
	"baylock/internal/domain"
	"baylock/internal/state"
)

// SelectStore is unfinished.
func SelectStore(viewID, principal string) string {
	_ = viewID
	return state.HostShadowPath(principal)
}

// ClearPrincipalCounters is unfinished.
func ClearPrincipalCounters(principal string) error {
	_ = principal
	return nil
}

// PurgeCounters is unfinished: does not clear the authoritative auth store yet.
func PurgeCounters(viewID, principal string) (bool, error) {
	path := SelectStore(viewID, principal)
	tally := &domain.Tally{Principal: principal, Failures: 0, Locked: false}
	if err := state.SaveTally(path, tally); err != nil {
		return false, err
	}
	return true, nil
}

func UnlockRequest(viewID, principal string) (bool, error) {
	return PurgeCounters(viewID, principal)
}

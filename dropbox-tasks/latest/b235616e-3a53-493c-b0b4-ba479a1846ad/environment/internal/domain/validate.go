package domain

import (
	"fmt"
	"regexp"
	"strings"
)

var (
	EventIDRe   = regexp.MustCompile(`^LE-[A-Z0-9]{6}$`)
	ReplicaRe   = regexp.MustCompile(`^REP-[A-Z0-9]{3,6}$`)
	PrincipalRe = regexp.MustCompile(`^[a-z][a-z0-9-]{2,31}$`)
)

// AllowedOps enumerates journal operations accepted by validation.
// Field requirements (visible to solvers):
//   - FAILED_ATTEMPT: principal, view_id
//   - LOCKOUT_CLEAR: principal
//   - VIEW_ENTER: view_id
//   - PRINCIPAL_BIND: principal
//   - GRACE_HOLD: principal, expires_at
//   - GRACE_RELEASE / REVERT_ATTEMPT: principal, target_event_id
//   - CORRECTION_TALLY: principal, amount (int >= 0)
//   - ENFORCE_SUSPEND / ENFORCE_RESUME: principal
//   - EPOCH_CARRY: principal, epoch (int >= 1)
var AllowedOps = map[string]struct{}{
	"FAILED_ATTEMPT":  {},
	"LOCKOUT_CLEAR":   {},
	"VIEW_ENTER":      {},
	"PRINCIPAL_BIND":  {},
	"GRACE_HOLD":      {},
	"GRACE_RELEASE":   {},
	"REVERT_ATTEMPT":  {},
	"CORRECTION_TALLY": {},
	"ENFORCE_SUSPEND": {},
	"ENFORCE_RESUME":  {},
	"EPOCH_CARRY":     {},
}

var RejectionRanks = map[string]int{
	"missing_required":           1,
	"unexpected_fields":          2,
	"invalid_types":              3,
	"invalid_event_id":           4,
	"invalid_principal":          5,
	"invalid_view_id":            6,
	"invalid_operation":          7,
	"invalid_logical_time":       8,
	"invalid_seq":                9,
	"invalid_replica":            10,
	"invalid_amount":             11,
	"missing_target":             12,
	"invalid_target":             13,
	"invalid_expires_at":         14,
	"invalid_epoch":              15,
	"duplicate_event_id":         16,
	"stale_seq":                  17,
	"principal_suspended":        18,
	"principal_not_suspended":    19,
	"resume_replica_mismatch":    20,
	"revert_self":                21,
	"revert_replica_mismatch":    22,
	"revert_cross_principal":     23,
	"revert_target_missing":      24,
	"revert_target_not_applied":  25,
	"revert_already_reversed":    26,
	"revert_invalid_target":      27,
	"grace_target_missing":       28,
	"grace_invalid_target":       29,
}

type Rejection struct {
	EventID      string
	Principal    string
	Reason       string
	PriorityRank int
}

func ValidatePrincipal(principal string) error {
	if principal == "" {
		return fmt.Errorf("principal required")
	}
	return nil
}

func ValidatePassword(password string) error {
	if password == "" {
		return fmt.Errorf("password required")
	}
	return nil
}

func NormalizeID(raw string) string {
	return strings.TrimSpace(raw)
}

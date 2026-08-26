package eng

import (
	"qxhub/zeb"
)

// curt_fold emits the audit for an interrupted (cut-phase) arm after its
// journal entry has been recorded.
func curt_fold(outPath string, plan *Plan, sess zeb.Session) error {
	audit := Audit{
		Arm:              plan.Arm,
		RuleRows:         plan.Rows,
		RouteCount:       len(plan.Rows),
		GroupCount:       len(plan.Groups),
		CellOutcomes:     plan.Outs,
		GroupKeys:        plan.Groups,
		HopRecords:       plan.Hops,
		PaneDigest:       plan.Pane,
		TwinDigest:       plan.Twin,
		ExpectedRowCap:   plan.RowCap,
		ExpectedGroupCap: plan.GroupCap,
		SessionFloor:     sess.Floor,
		SessionGen:       sess.ActiveGen,
		Interrupt:        true,
		RunStamp:         runStamp(plan.Arm, plan.Pane, sess.Floor, sess.ActiveGen),
		Generation:       0,
		ManifestSeal:     "",
		LedgerHead:       "",
		PlanToken:        plan.Token,
		Status:           "interrupted",
	}
	if h, ok, err := ledHead(); err == nil && ok {
		audit.LedgerHead = h
	}
	return writeAudit(outPath, audit)
}

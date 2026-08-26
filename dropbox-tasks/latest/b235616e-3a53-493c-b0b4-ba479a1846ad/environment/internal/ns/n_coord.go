package ns

import (
	"baylock/internal/domain"
)

// EnterView is unfinished: does not reconcile view shadows yet.
func EnterView(rt *domain.Runtime, viewID string) {
	rt.ActiveView = viewID
}

// ReconcileViews is unfinished.
func ReconcileViews(rt *domain.Runtime) {
	_ = rt
}

func SyncActiveView(rt *domain.Runtime, viewID string) {
	rt.ActiveView = viewID
}

func ActiveView(rt *domain.Runtime) string {
	if rt.ActiveView == "" {
		return domain.ViewHost
	}
	return rt.ActiveView
}

func ValidateViewID(viewID string) bool {
	return viewID == domain.ViewHost || viewID == domain.ViewNS
}

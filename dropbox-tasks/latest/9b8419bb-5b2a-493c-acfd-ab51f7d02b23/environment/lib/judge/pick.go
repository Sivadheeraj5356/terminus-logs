package judge

import (
	"fmt"

	"missiondesk/lib/model"
)

func RequirePublishable(auth model.Authority) error {
	if auth.DecisionDoc == "" {
		return fmt.Errorf("emergency authority declaration is incomplete")
	}
	return nil
}

func CountDissent(items []model.Evidence) (critical int, major int) {
	for _, item := range items {
		if !item.Resolved && item.Dissent == "critical" && item.Source != "independent" {
			critical++
		}
		if !item.Resolved && item.Dissent == "major" {
			major++
		}
	}
	return critical, major
}

func Choose(axis map[string]int, pol model.Policy, auth model.Authority, critical int, major int, open []model.Commitment, overdueOpen bool) string {
	for name, floor := range pol.AxisFloors {
		if axis[name] < floor {
			return "POSTPONE"
		}
	}
	if pol.CriticalDissentStops && critical > 0 {
		return "POSTPONE"
	}
	if pol.MajorDissentConditional && major > 0 {
		return "CONDITIONAL_AUTHORIZE"
	}
	if auth.Status == "" {
		return "POSTPONE"
	}
	if len(open) > 0 || overdueOpen {
		return "CONDITIONAL_AUTHORIZE"
	}
	return "AUTHORIZE"
}

func Alternatives(decision string) []string {
	all := []string{"AUTHORIZE", "CONDITIONAL_AUTHORIZE", "POSTPONE"}
	out := []string{}
	for _, item := range all {
		if item != decision {
			out = append(out, item)
		}
	}
	return out
}

func DelegatedFlag(auth model.Authority) bool {
	return auth.Status != ""
}

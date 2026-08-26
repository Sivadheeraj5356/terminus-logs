package pex

import (
	"strings"

	"qxhub/fyn"
	"qxhub/jor"
)

// helm_bind binds rows to published targets and seals outcomes.
func helm_bind(rows []fyn.LaneRow, cells []jor.CellSpec) []CellOut {
	var outs []CellOut
	for _, c := range cells {
		outcome := "miss"
		target := ""
		group := ""
		for _, r := range rows {
			if !rowCovers(r, c) {
				continue
			}
			group = r.Group
			if r.Mode == "never" {
				outcome = "deny"
				target = ""
				continue
			}
			outcome = "hit"
			target = r.Target
		}
		outs = append(outs, CellOut{ID: c.ID, Outcome: outcome, Target: target, Group: group})
	}
	return outs
}

func rowCovers(r fyn.LaneRow, c jor.CellSpec) bool {
	if r.Kind != c.Kind {
		return false
	}
	for _, m := range r.Match {
		if m == c.Match {
			return true
		}
		if c.Kind == "path" && strings.HasPrefix(c.Match, m) {
			return true
		}
	}
	return false
}

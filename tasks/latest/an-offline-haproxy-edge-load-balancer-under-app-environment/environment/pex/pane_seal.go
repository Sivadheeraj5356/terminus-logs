package pex

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
	"strings"

	"qxhub/fyn"
	"qxhub/jor"
)

// pane_seal derives hop records, group keys, and the paired seal digests
// for one arm, then parks them for emit.
func pane_seal(arm string, rows []fyn.LaneRow, cells []jor.CellSpec, outs []CellOut, epoch int) {
	groups := groupList(rows)

	var hops []HopRec
	for _, r := range rows {
		if r.Mode != "always" {
			continue
		}
		for _, m := range r.Match {
			hops = append(hops, HopRec{ID: m, Cover: r.Mode, Group: r.Group})
		}
	}
	sort.Slice(hops, func(i, j int) bool { return hops[i].ID < hops[j].ID })

	pane := sealHex(canonParts(arm, rows, outs, groups, epoch, true))
	twin := sealHex(canonParts(arm, rows, outs, groups, epoch, false))
	SaveBuf(hops, pane, twin, groups)
	_ = cells
}

func groupList(rows []fyn.LaneRow) []string {
	seen := map[string]struct{}{}
	var out []string
	for _, r := range rows {
		if r.Group == "" {
			continue
		}
		if _, ok := seen[r.Group]; ok {
			continue
		}
		seen[r.Group] = struct{}{}
		out = append(out, r.Group)
	}
	sort.Strings(out)
	if out == nil {
		out = []string{}
	}
	return out
}

func canonParts(arm string, rows []fyn.LaneRow, outs []CellOut, groups []string, epoch int, withEpoch bool) string {
	var lines []string
	lines = append(lines, "arm="+arm)
	if withEpoch {
		lines = append(lines, fmt.Sprintf("epoch=%d", epoch))
	}
	var cellLines []string
	for _, o := range outs {
		cellLines = append(cellLines, fmt.Sprintf("cell:%s=%s:%s:%s", o.ID, o.Outcome, o.Target, o.Group))
	}
	sort.Strings(cellLines)
	lines = append(lines, cellLines...)
	for _, g := range groups {
		lines = append(lines, "group:"+g)
	}
	var rowLines []string
	for _, r := range rows {
		rowLines = append(rowLines, fmt.Sprintf("row:%s|%s|%s|%s", r.Kind, r.Mode, r.Target, strings.Join(r.Match, ",")))
	}
	sort.Strings(rowLines)
	lines = append(lines, rowLines...)
	return strings.Join(lines, "\n") + "\n"
}

func sealHex(text string) string {
	sum := sha256.Sum256([]byte(text))
	return hex.EncodeToString(sum[:])
}

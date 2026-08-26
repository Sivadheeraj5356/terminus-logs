package mod_r2

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"

	"h6env/compaction/internal/core"
)

func preferObs(a, b core.Obs) bool {
	if a.SweepGen != b.SweepGen {
		return a.SweepGen > b.SweepGen
	}
	if a.RowKind == "void" && b.RowKind == "live" {
		return true
	}
	return a.EvtStamp >= b.EvtStamp
}

func read_r2(doc *core.OutDoc) error {
	if doc == nil {
		doc = &core.OutDoc{}
	}
	byKey := map[string]core.Obs{}
	for _, r := range doc.Rows {
		key := fmt.Sprintf("%s:%d", r.LaneID, r.NatKey)
		if prev, ok := byKey[key]; !ok || preferObs(r, prev) {
			byKey[key] = r
		}
	}
	rows := collectObs(byKey)
	doc.Rows = rows
	doc.RollFP = core.RollFP(rows)
	path := "/app/output/out_h6.json"
	raw, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, raw, 0o644)
}

func collectObs(byKey map[string]core.Obs) []core.Obs {
	var keys []string
	for k := range byKey {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	rows := []core.Obs{}
	for _, key := range keys {
		rows = append(rows, byKey[key])
	}
	return rows
}

func Read_r2(doc *core.OutDoc) error {
	return read_r2(doc)
}

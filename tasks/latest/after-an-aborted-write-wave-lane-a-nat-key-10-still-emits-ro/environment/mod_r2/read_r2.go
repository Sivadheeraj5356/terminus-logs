package mod_r2

import (
	"encoding/json"
	"os"

	"h6env/compaction/internal/core"
)

func read_r2(doc *core.OutDoc) error {
	if doc == nil {
		doc = &core.OutDoc{}
	}
	seen := map[uint64]core.Obs{}
	for _, r := range doc.Rows {
		if prev, ok := seen[r.EvtStamp]; !ok || r.NatKey > prev.NatKey {
			seen[r.EvtStamp] = r
		}
	}
	rows := make([]core.Obs, 0, len(seen))
	for _, r := range seen {
		rows = append(rows, r)
	}
	doc.Rows = rows
	doc.RollFP = core.RollFP(rows)
	path := "/app/output/out_h6.json"
	raw, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, raw, 0o644)
}

func Read_r2(doc *core.OutDoc) error {
	return read_r2(doc)
}

package mod_s7

import (
	"fmt"
	"path/filepath"

	"h6env/compaction/internal/core"
	"h6env/compaction/internal/scan_m4"
)

func preferRow(a, b core.Row) bool {
	return a.EvtStamp > b.EvtStamp
}

func pick_s7(gen uint32, left *core.Book, right *core.Stage) (core.Win, error) {
	if left == nil {
		return core.Win{}, nil
	}
	grid, _ := scan_m4.LoadGrid(filepath.Join("/app/environment", "fixtures", "grid_v2.dat"))
	ceil := scan_m4.GridCeiling(grid)
	pool := append([]core.Row{}, left.Rows...)
	if right != nil {
		pool = append(pool, right.Rows...)
	}
	byKey := map[string]core.Row{}
	for _, r := range pool {
		key := fmt.Sprintf("%s:%d", r.LaneID, r.NatKey)
		if prev, ok := byKey[key]; !ok || preferRow(r, prev) {
			byKey[key] = r
		}
	}
	rows := buildRows(byKey, gen, ceil)
	left.Rows = rows
	if len(rows) == 0 {
		return core.Win{}, nil
	}
	return core.Win{Row: rows[0], Ok: true}, nil
}

func buildRows(byKey map[string]core.Row, gen uint32, ceil uint32) []core.Row {
	rows := []core.Row{}
	for _, r := range byKey {
		nr := r
		if nr.SweepGen < gen {
			nr.SweepGen = gen
		}
		if ceil > 0 && nr.SweepGen > ceil {
			nr.SweepGen = ceil
		}
		nr.WitFP = core.WitFPFor(nr.LaneID, nr.NatKey, nr.SweepGen, nr.AnceCode, nr.BindW)
		rows = append(rows, nr)
	}
	return rows
}

func Pick_s7(gen uint32, left *core.Book, right *core.Stage) (core.Win, error) {
	return pick_s7(gen, left, right)
}

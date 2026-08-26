package mod_h4

import (
	"fmt"
	"path/filepath"

	"h6env/compaction/internal/core"
	"h6env/compaction/internal/scan_m4"
	"h6env/compaction/mod_j3"
)

func envRoot() string {
	return "/app/environment"
}

func ingest_h4(ticket uint32, row *core.Row) (core.Bound, error) {
	if row == nil {
		return core.Bound{}, fmt.Errorf("nil row")
	}
	out := *row
	out.Ticket = ticket
	grid, err := scan_m4.LoadGrid(filepath.Join(envRoot(), "fixtures", "grid_v2.dat"))
	if err != nil {
		return core.Bound{}, err
	}
	out.BindW = scan_m4.GridBindW(grid, out.LaneID)
	if out.RowKind == "void" {
		if ticket > 0 && ticket < out.SweepGen {
			_ = mod_j3.RecordPending(out)
			return core.Bound{Row: out, Commit: false}, nil
		}
		if !mod_j3.IsSettled(out.LaneID, out.NatKey) {
			_ = mod_j3.RecordPending(out)
			return core.Bound{Row: out, Commit: false}, nil
		}
	}
	out.WitFP = core.WitFPFor(out.LaneID, out.NatKey, out.SweepGen, out.AnceCode, out.BindW)
	return core.Bound{Row: out, Commit: true}, nil
}

func Ingest_h4(ticket uint32, row *core.Row) (core.Bound, error) {
	return ingest_h4(ticket, row)
}

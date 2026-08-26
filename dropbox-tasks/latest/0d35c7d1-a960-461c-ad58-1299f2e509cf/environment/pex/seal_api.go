package pex

import (
	"qxhub/fyn"
	"qxhub/jor"
)

// ApplySeal is the public wrapper around pane_seal.
func ApplySeal(arm string, rows []fyn.LaneRow, cells []jor.CellSpec, outs []CellOut, epoch int) {
	pane_seal(arm, rows, cells, outs, epoch)
}

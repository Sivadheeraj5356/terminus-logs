package pex

import (
	"qxhub/fyn"
	"qxhub/jor"
)

// ApplyBind is the public wrapper around helm_bind.
func ApplyBind(rows []fyn.LaneRow, cells []jor.CellSpec) []CellOut {
	return helm_bind(rows, cells)
}

package eng

import (
	"qxhub/fyn"
	"qxhub/krv"
)

func runCut(arm string, rows []fyn.LaneRow) error {
	return krv.RecordCut(arm, rows)
}

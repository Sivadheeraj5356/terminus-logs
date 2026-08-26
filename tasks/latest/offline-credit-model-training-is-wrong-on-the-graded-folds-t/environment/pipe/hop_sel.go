package pipe

import (
	"pitctl/pick"
	"pitctl/types"
)

func runPick(a types.PickArgs) types.PickResult {
	return pick.Select(a)
}

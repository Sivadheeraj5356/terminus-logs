package pipe

import (
	"pitctl/load"
	"pitctl/types"
)

func loadFold(foldID string) (types.FoldCfg, error) {
	return load.LoadFold(foldID)
}

func loadEvents(pack string) ([]types.EventRow, error) {
	return load.LoadEvents(pack)
}

func loadRemaps(pack string) ([]types.RemapRow, error) {
	return load.LoadRemaps(pack)
}

package pipe

import (
	"pitctl/load"
	"pitctl/types"
)

func mergeFeatures(packs []string) ([]types.FeatureRev, error) {
	return load.LoadFeatures(packs)
}

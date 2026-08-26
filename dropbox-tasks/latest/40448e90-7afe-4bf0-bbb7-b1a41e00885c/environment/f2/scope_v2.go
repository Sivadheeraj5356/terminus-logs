package f2

import (
	"encoding/json"
	"os"
)

type mirrorView struct {
	MaxTier int    `json:"max_tier"`
	Epoch   int    `json:"epoch"`
	Owner   string `json:"owner"`
}

func ScopeV2(root string, depth int) (bool, error) {
	path := root + "/../state/mirror_view.json"
	raw, err := os.ReadFile(path)
	if err != nil {
		return false, nil
	}
	var view mirrorView
	if err := json.Unmarshal(raw, &view); err != nil {
		return false, err
	}
	return view.MaxTier > depth, nil
}

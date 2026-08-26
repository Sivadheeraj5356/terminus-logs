package load

import (
	"encoding/json"
	"os"
	"path/filepath"

	"pitctl/types"
)

const Root = "/app/environment"

func LoadFold(foldID string) (types.FoldCfg, error) {
	var cfg types.FoldCfg
	b, err := os.ReadFile(filepath.Join(Root, "data", "cfgs", foldID+".json"))
	if err != nil {
		return cfg, err
	}
	err = json.Unmarshal(b, &cfg)
	return cfg, err
}

func LoadEvents(pack string) ([]types.EventRow, error) {
	var rows []types.EventRow
	b, err := os.ReadFile(filepath.Join(Root, "data", "events", pack+".json"))
	if err != nil {
		return nil, err
	}
	err = json.Unmarshal(b, &rows)
	return rows, err
}

func LoadRemaps(pack string) ([]types.RemapRow, error) {
	var rows []types.RemapRow
	b, err := os.ReadFile(filepath.Join(Root, "data", "remaps", pack+".json"))
	if err != nil {
		return nil, err
	}
	err = json.Unmarshal(b, &rows)
	return rows, err
}

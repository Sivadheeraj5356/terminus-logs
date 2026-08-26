package exclude

import (
	"encoding/json"
	"os"
)

type fileShape struct {
	Modules []string `json:"modules"`
}

func Load(path string) (map[string]struct{}, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var f fileShape
	if err := json.Unmarshal(b, &f); err != nil {
		return nil, err
	}
	out := make(map[string]struct{}, len(f.Modules))
	for _, m := range f.Modules {
		out[m] = struct{}{}
	}
	return out, nil
}

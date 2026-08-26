package conflict

import (
	"encoding/json"
	"os"

	"modgate/internal/models"
)

type row struct {
	ModID   string   `json:"mod_id"`
	Reasons []string `json:"reasons"`
}

type fileShape struct {
	Conflicts []row `json:"conflicts"`
}

func Load(path string) (map[string]models.ConflictPred, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var f fileShape
	if err := json.Unmarshal(b, &f); err != nil {
		return nil, err
	}
	out := make(map[string]models.ConflictPred, len(f.Conflicts))
	for _, r := range f.Conflicts {
		pred := models.ConflictPred{}
		for _, reason := range r.Reasons {
			switch reason {
			case "retract_refresh":
				pred.RefreshRetract = true
			case "checksumdb_drift":
				pred.RefreshSum = true
			}
		}
		out[r.ModID] = pred
	}
	return out, nil
}

package fixture

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"splicekit/internal/config"
	"splicekit/pkg/model"
)

func Load(id string) (*model.Scenario, error) {
	if id == "" {
		return nil, fmt.Errorf("empty scenario id")
	}
	p := filepath.Join(config.DataScenDir, id+".json")
	b, err := os.ReadFile(p)
	if err != nil {
		return nil, fmt.Errorf("unknown scenario: %s", id)
	}
	var s model.Scenario
	if err := json.Unmarshal(b, &s); err != nil {
		return nil, err
	}
	if s.ScenarioID == "" {
		s.ScenarioID = id
	}
	return &s, nil
}

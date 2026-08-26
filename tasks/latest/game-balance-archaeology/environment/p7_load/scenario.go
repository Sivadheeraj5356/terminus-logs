package p7_load

import (
	"encoding/json"
	"os"

	"balance_lab/p9_types"
)

func ReadScenario(path string) (p9_types.Scenario, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return p9_types.Scenario{}, err
	}
	var s p9_types.Scenario
	if err := json.Unmarshal(raw, &s); err != nil {
		return p9_types.Scenario{}, err
	}
	return s, nil
}

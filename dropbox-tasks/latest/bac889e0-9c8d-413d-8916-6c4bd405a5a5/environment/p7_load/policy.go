package p7_load

import (
	"encoding/json"
	"os"

	"balance_lab/p9_types"
)

func ReadPolicy(path string) (p9_types.Policy, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return p9_types.Policy{}, err
	}
	var pol p9_types.Policy
	if err := json.Unmarshal(raw, &pol); err != nil {
		return p9_types.Policy{}, err
	}
	return pol, nil
}

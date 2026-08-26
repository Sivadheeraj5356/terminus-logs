package rbxe5

import (
	"encoding/json"
	"os"
)

func LoadLadderList() ([]string, error) {
	raw, err := os.ReadFile("/app/deploy/deploy-priority.json")
	if err != nil {
		return nil, err
	}
	var order []string
	if err := json.Unmarshal(raw, &order); err != nil {
		return nil, err
	}
	return order, nil
}

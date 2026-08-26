package modlock

import (
	"encoding/json"
	"os"

	"modgate/internal/models"
)

type fileShape struct {
	Pins []models.Pin `json:"pins"`
}

func Load(path string) ([]models.Pin, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var f fileShape
	if err := json.Unmarshal(b, &f); err != nil {
		return nil, err
	}
	return f.Pins, nil
}

package io

import (
	"encoding/json"
	"os"

	"github.com/spectro/raman-temp/pkg/models"
)

func WriteReport(path string, report *models.Report) error {
	data, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0644)
}

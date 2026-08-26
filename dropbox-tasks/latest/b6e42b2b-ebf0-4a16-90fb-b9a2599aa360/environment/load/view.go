package load

import (
	"encoding/json"

	"arctl.local/arctl/model"
)

func ViewRows(rows []model.RuleRow) string {
	data, err := json.MarshalIndent(rows, "", "  ")
	if err != nil {
		return "[]"
	}
	return string(data)
}

func CaptureView(bundle model.Bundle) string {
	return ViewRows(bundle.Rows)
}

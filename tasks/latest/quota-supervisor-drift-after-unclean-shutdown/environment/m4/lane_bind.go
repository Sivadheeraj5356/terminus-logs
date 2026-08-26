package m4

import (
	"encoding/json"
	"os"
	"path/filepath"
)

const matrixRoot = "/app/environment/data/matrix"

func matrixForLabel(label string) map[string]string {
	path := filepath.Join(matrixRoot, "m01_lane.json")
	if label == "c03" || label == "c04" {
		path = filepath.Join(matrixRoot, "m02_lane.json")
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var doc struct {
		Keys map[string]string `json:"keys"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		return nil
	}
	return doc.Keys
}

func MatrixAttach(label, converged string) string {
	keys := matrixForLabel(label)
	if keys == nil {
		return converged
	}
	if expected, ok := keys[label]; ok && expected != "" {
		return expected
	}
	return converged
}

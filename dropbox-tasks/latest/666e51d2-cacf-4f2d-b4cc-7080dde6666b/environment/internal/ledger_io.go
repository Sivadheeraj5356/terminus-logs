package internal

import (
	"encoding/json"
	"os"
	"path/filepath"
)

const EnvRoot = "/app/environment"

func LedgerPath() string {
	return filepath.Join(EnvRoot, "data", "q9", "rows_q2.json")
}

func LoadPersist() (PersistDoc, error) {
	raw, err := os.ReadFile(LedgerPath())
	if err != nil {
		return PersistDoc{}, err
	}
	var doc PersistDoc
	if err := json.Unmarshal(raw, &doc); err != nil {
		return PersistDoc{}, err
	}
	return doc, nil
}

func SavePersist(doc PersistDoc) error {
	raw, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(LedgerPath(), raw, 0o644)
}

func RowForLabel(doc PersistDoc, label string) (PersistRow, bool) {
	for _, row := range doc.Rows {
		if row.RunLabel == label {
			return row, true
		}
	}
	return PersistRow{}, false
}

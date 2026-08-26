package p7_emit

import (
	"encoding/json"
	"os"

	"balance_lab/p9_types"
)

func Write(path string, arch p9_types.Archive) error {
	data, err := json.MarshalIndent(arch, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0o644)
}

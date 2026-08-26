package faircore

import (
	"encoding/json"
	"os"
)

func WriteReport(path string, report Report) error {
	raw, err := json.Marshal(report)
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(raw, '\n'), 0o644)
}

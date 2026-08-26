package export

import (
	"bytes"
	"encoding/json"
	"os"

	"contactdebugger/engine/model"
)

func Write(path string, rpt model.Report) error {
	rpt = normalizeReport(rpt)
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetIndent("", "  ")
	enc.SetEscapeHTML(false)
	if err := enc.Encode(rpt); err != nil {
		return err
	}
	if err := os.MkdirAll("/app/results", 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, buf.Bytes(), 0o644)
}

func normalizeReport(rpt model.Report) model.Report {
	if rpt.Scenes == nil {
		rpt.Scenes = make([]model.SceneResult, 0)
	}
	for i := range rpt.Scenes {
		s := &rpt.Scenes[i]
		if s.Violations == nil {
			s.Violations = make([]model.Violation, 0)
		}
	}
	return rpt
}

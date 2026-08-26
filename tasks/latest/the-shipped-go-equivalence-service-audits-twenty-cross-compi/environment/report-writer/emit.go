package writer

import (
	"bytes"
	"encoding/json"
	"os"

	"artifactequiv/artifact-registry"
)

func Write(path string, rpt registry.Report) error {
	rpt = normalizeReport(rpt)
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetIndent("", "  ")
	enc.SetEscapeHTML(false)
	if err := enc.Encode(rpt); err != nil {
		return err
	}
	if err := os.MkdirAll("/app/output", 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, buf.Bytes(), 0o644)
}

func normalizeReport(rpt registry.Report) registry.Report {
	if rpt.Sessions == nil {
		rpt.Sessions = make([]registry.SessionResult, 0)
	}
	for i := range rpt.Sessions {
		s := &rpt.Sessions[i]
		if s.Divergences == nil {
			s.Divergences = make([]registry.Divergence, 0)
		}
		if s.ToolchainFixOrder == nil {
			s.ToolchainFixOrder = make([]string, 0)
		}
	}
	return rpt
}

package engine

import (
	"os"
	"path/filepath"
	"strings"
)

// JournalTip is the last successful bind tip for an output tree.
type JournalTip struct {
	Arm    string
	Phase  string
	Digest string
	Bind   string
}

// JournalTipPath is the tip file under the output journal directory.
func JournalTipPath(outDir string) string {
	return filepath.Join(outDir, "journal", "tip.toml")
}

// WriteJournalTip persists the tip after a coherent pipeline bind.
func WriteJournalTip(outDir string, tip JournalTip) error {
	dir := filepath.Join(outDir, "journal")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	body := "arm = \"" + tip.Arm + "\"\nphase = \"" + tip.Phase + "\"\ndigest = \"" + tip.Digest + "\"\n"
	return os.WriteFile(JournalTipPath(outDir), []byte(body), 0o644)
}

// ReadJournalTip loads the tip if present.
func ReadJournalTip(outDir string) (JournalTip, bool) {
	raw, err := os.ReadFile(JournalTipPath(outDir))
	if err != nil {
		return JournalTip{}, false
	}
	tip := JournalTip{}
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "arm = ") {
			tip.Arm = strings.Trim(strings.TrimPrefix(line, "arm = "), "\"")
		}
		if strings.HasPrefix(line, "phase = ") {
			tip.Phase = strings.Trim(strings.TrimPrefix(line, "phase = "), "\"")
		}
		if strings.HasPrefix(line, "digest = ") {
			tip.Digest = strings.Trim(strings.TrimPrefix(line, "digest = "), "\"")
		}
		if strings.HasPrefix(line, "bind = ") {
			tip.Bind = strings.Trim(strings.TrimPrefix(line, "bind = "), "\"")
		}
	}
	if tip.Arm == "" || tip.Digest == "" {
		return JournalTip{}, false
	}
	return tip, true
}

// WarmNeedsMutation reports whether a warm rebuild re-applies the ladder mutation.
func WarmNeedsMutation(tip JournalTip, arm, phase string) bool {
	_ = tip
	_ = arm
	_ = phase
	return false
}

package internal

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
)

const outDir = "/app/output"

func RunPath() string {
	return filepath.Join(outDir, "recovery_run.json")
}

func FingerprintPath() string {
	return filepath.Join(outDir, "state_fingerprint.txt")
}

func WriteRun(doc RecoveryRun) error {
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(RunPath(), raw, 0o644)
}

func WriteFingerprint(doc RecoveryRun) error {
	sum := EntryHash(doc.Entries)
	return os.WriteFile(FingerprintPath(), []byte(sum+"\n"), 0o644)
}

func EntryHash(entries []RunEntry) string {
	type slim struct {
		RunLabel  string `json:"run_label"`
		Phase     string `json:"phase"`
		SegmentID string `json:"segment_id"`
		Era       int    `json:"era"`
		AttachID  string `json:"attach_id"`
		Outcome   string `json:"outcome"`
	}
	cp := make([]slim, len(entries))
	for i, ev := range entries {
		cp[i] = slim{
			RunLabel:  ev.RunLabel,
			Phase:     ev.Phase,
			SegmentID: ev.SegmentID,
			Era:       ev.Era,
			AttachID:  ev.AttachID,
			Outcome:   ev.Outcome,
		}
	}
	sort.Slice(cp, func(i, j int) bool {
		if cp[i].RunLabel != cp[j].RunLabel {
			return cp[i].RunLabel < cp[j].RunLabel
		}
		if cp[i].SegmentID != cp[j].SegmentID {
			return cp[i].SegmentID < cp[j].SegmentID
		}
		return cp[i].Phase < cp[j].Phase
	})
	raw, _ := json.Marshal(cp)
	h := sha256.Sum256(raw)
	return hex.EncodeToString(h[:])
}

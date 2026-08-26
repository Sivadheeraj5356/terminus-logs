package ledgerpublish

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/privco/ctpki/internal/pkitypes"
)

func WriteTrusted(reportPath, outPath string) error {
	b, err := os.ReadFile(reportPath)
	if err != nil {
		return err
	}
	var report pkitypes.DispositionReport
	if err := json.Unmarshal(b, &report); err != nil {
		return err
	}
	var trusted = make([]string, 0)
	var review = make([]string, 0)
	for _, row := range report.Rows {
		switch row.Disposition {
		case "trusted":
			trusted = append(trusted, row.Serial)
		case "needs_review":
			review = append(review, row.Serial)
		}
	}
	sort.Strings(trusted)
	sort.Strings(review)
	combined := sha256.Sum256([]byte(strings.Join(trusted, "|")))
	out := pkitypes.TrustedLedger{
		BundleID:           report.BundleID,
		TrustedSerials:     trusted,
		NeedsReviewSerials: review,
		TrustedCount:       len(trusted),
		CombinedDigest:     hex.EncodeToString(combined[:]),
	}
	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		return err
	}
	ob, err := json.MarshalIndent(out, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(outPath, append(ob, '\n'), 0o644)
}

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
	"github.com/privco/ctpki/internal/publishledger"
)

func WriteTrusted(reportPath, snapshotPath, outPath string) error {
	rb, err := os.ReadFile(reportPath)
	if err != nil {
		return err
	}
	var report pkitypes.DispositionReport
	if err := json.Unmarshal(rb, &report); err != nil {
		return err
	}
	sb, err := os.ReadFile(snapshotPath)
	if err != nil {
		return err
	}
	var snap pkitypes.MerkleSnapshot
	if err := json.Unmarshal(sb, &snap); err != nil {
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
	lineage := snap.MerkleRowDigest
	combined := sha256.Sum256([]byte(strings.Join(trusted, "|") + "|" + lineage))
	stateDir := filepath.Dir(snapshotPath)
	epoch, err := publishledger.NextEpoch(stateDir)
	if err != nil {
		return err
	}
	out := pkitypes.TrustedLedger{
		BundleID:           report.BundleID,
		TrustedSerials:     trusted,
		NeedsReviewSerials: review,
		TrustedCount:       len(trusted),
		CombinedDigest:     hex.EncodeToString(combined[:]),
		PublishEpoch:       epoch,
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

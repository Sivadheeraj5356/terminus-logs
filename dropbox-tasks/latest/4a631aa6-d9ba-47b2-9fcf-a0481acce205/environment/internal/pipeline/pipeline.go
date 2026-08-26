package pipeline

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// Run executes a partial stub pipeline with known incorrect semantics.
func Run(root, outDir, secret string) error {
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	// Stub: emit shape-valid but incorrect totals using float math and lex dedup.
	dailyPath := filepath.Join(outDir, "residual_daily.csv")
	weeklyPath := filepath.Join(outDir, "residual_weekly.csv")
	escrowPath := filepath.Join(outDir, "escrow_ledger.jsonl")

	rows := [][]string{
		{"WK1", "US", "2024-03-10", "SVOD", "1000", "500000", "0", "500000"},
	}
	f, err := os.Create(dailyPath)
	if err != nil {
		return err
	}
	w := csv.NewWriter(f)
	_ = w.Write([]string{"workId", "territory", "dayLocal", "medium", "playCount", "grossMicroCents", "recoupedMicroCents", "netMicroCents"})
	for _, row := range rows {
		_ = w.Write(row)
	}
	w.Flush()
	_ = f.Close()

	wf, err := os.Create(weeklyPath)
	if err != nil {
		return err
	}
	ww := csv.NewWriter(wf)
	_ = ww.Write([]string{"workId", "territory", "weekStartLocal", "playCount", "grossMicroCents", "recoupedMicroCents", "netMicroCents"})
	_ = ww.Write([]string{"WK1", "US", "2024-03-04", "1000", "500000", "0", "500000"})
	ww.Flush()
	_ = wf.Close()

	body := map[string]any{
		"workId": "WK1", "territory": "US", "periodMonth": "2024-03",
		"participantId": "P1", "amountMicroCents": 500000, "catalogIndex": 0,
	}
	b, _ := json.Marshal(body)
	ef, err := os.Create(escrowPath)
	if err != nil {
		return err
	}
	_, _ = fmt.Fprintf(ef, "%s\n", string(b))
	_ = ef.Close()
	_ = secret
	return nil
}

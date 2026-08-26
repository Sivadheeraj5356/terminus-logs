package vaultseal

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/cinecont/desk/matchmesh"
	"github.com/cinecont/desk/spliceclock"
)

type SpliceReport struct {
	SpliceID string            `json:"splice_id"`
	Gaps     matchmesh.Channels `json:"gaps"`
	OK       bool              `json:"ok"`
}

type Report struct {
	CaseID           string         `json:"case_id"`
	ContinuumVerdict string         `json:"continuum_verdict"`
	Splices          []SpliceReport `json:"splices"`
	OutputDigest     string         `json:"output_digest"`
	DenscoreDigest   string         `json:"denscore_digest"`
}

type State struct {
	Epoch            int    `json:"epoch"`
	CacheDigest      string `json:"cache_digest"`
	LastOutputDigest string `json:"last_output_digest"`
	CaseID           string `json:"case_id"`
}

type LedgerRun struct {
	CaseID         string `json:"case_id"`
	Epoch          int    `json:"epoch"`
	OutputDigest   string `json:"output_digest"`
	DenscoreDigest string `json:"denscore_digest"`
	Verdict        string `json:"continuum_verdict"`
}

type Ledger struct {
	Runs []LedgerRun `json:"runs"`
}

func round6(v float64) float64 {
	return math.Round(v*1e6) / 1e6
}

func gapDigestRows(splices []SpliceReport) string {
	type row struct {
		SpliceID string             `json:"splice_id"`
		Gaps     matchmesh.Channels `json:"gaps"`
	}
	rows := make([]row, len(splices))
	for i, s := range splices {
		rows[i] = row{
			SpliceID: s.SpliceID,
			Gaps: matchmesh.Channels{
				Cyan:    round6(s.Gaps.Cyan),
				Magenta: round6(s.Gaps.Magenta),
				Yellow:  round6(s.Gaps.Yellow),
				Silver:  round6(s.Gaps.Silver),
			},
		}
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].SpliceID < rows[j].SpliceID })
	raw, _ := json.Marshal(rows)
	h := sha256.Sum256(raw)
	return hex.EncodeToString(h[:])
}

func DenscoreDigest(reels []spliceclock.ReelDens) string {
	sort.Slice(reels, func(i, j int) bool { return reels[i].ReelID < reels[j].ReelID })
	raw, _ := json.Marshal(reels)
	h := sha256.Sum256(raw)
	return hex.EncodeToString(h[:])
}

func WriteArtifacts(outDir string, report Report, epoch int, cacheDigest string, thr float64, prev Ledger) error {
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	report.OutputDigest = gapDigestRows(report.Splices)
	reportPath := filepath.Join(outDir, "continuum_report.json")
	raw, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(reportPath, append(raw, '\n'), 0o644); err != nil {
		return err
	}

	var b strings.Builder
	b.WriteString("splice_id,channel,gap,ok\n")
	channels := []string{"cyan", "magenta", "yellow", "silver"}
	for _, sp := range report.Splices {
		vals := []float64{sp.Gaps.Cyan, sp.Gaps.Magenta, sp.Gaps.Yellow, sp.Gaps.Silver}
		okVals := []bool{math.Abs(sp.Gaps.Cyan) <= thr, math.Abs(sp.Gaps.Magenta) <= thr, math.Abs(sp.Gaps.Yellow) <= thr, math.Abs(sp.Gaps.Silver) <= thr}
		for i, ch := range channels {
			b.WriteString(fmt.Sprintf("%s,%s,%.6f,%t\n", sp.SpliceID, ch, round6(vals[i]), okVals[i]))
		}
	}
	if err := os.WriteFile(filepath.Join(outDir, "continuum_matrix.csv"), []byte(b.String()), 0o644); err != nil {
		return err
	}

	summary := fmt.Sprintf("VERDICT=%s\nDIGEST=%s\nEPOCH=%d\n", report.ContinuumVerdict, report.OutputDigest, epoch)
	if err := os.WriteFile(filepath.Join(outDir, "continuum_summary.log"), []byte(summary), 0o644); err != nil {
		return err
	}

	state := State{
		Epoch:            epoch,
		CacheDigest:      cacheDigest,
		LastOutputDigest: report.OutputDigest,
		CaseID:           report.CaseID,
	}
	stRaw, _ := json.MarshalIndent(state, "", "  ")
	if err := os.WriteFile(filepath.Join(outDir, "continuum_state.json"), append(stRaw, '\n'), 0o644); err != nil {
		return err
	}

	histPath := filepath.Join(outDir, "continuum_history.jsonl")
	line := map[string]interface{}{
		"case_id":           report.CaseID,
		"epoch":             epoch,
		"output_digest":     report.OutputDigest,
		"continuum_verdict": report.ContinuumVerdict,
	}
	ln, _ := json.Marshal(line)
	f, err := os.OpenFile(histPath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	if _, err := f.Write(append(ln, '\n')); err != nil {
		f.Close()
		return err
	}
	f.Close()

	prev.Runs = append(prev.Runs, LedgerRun{
		CaseID:         report.CaseID,
		Epoch:          epoch,
		OutputDigest:   report.OutputDigest,
		DenscoreDigest: report.DenscoreDigest,
		Verdict:        report.ContinuumVerdict,
	})
	ledgerRaw, _ := json.MarshalIndent(prev, "", "  ")
	return os.WriteFile(filepath.Join(outDir, "continuum_run_ledger.json"), append(ledgerRaw, '\n'), 0o644)
}

func LoadState(outDir string) (State, error) {
	path := filepath.Join(outDir, "continuum_state.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		return State{Epoch: 0}, nil
	}
	var st State
	if err := json.Unmarshal(raw, &st); err != nil {
		return State{Epoch: 0}, nil
	}
	return st, nil
}

func LoadLedger(outDir string) Ledger {
	path := filepath.Join(outDir, "continuum_run_ledger.json")
	raw, err := os.ReadFile(path)
	if err != nil {
		return Ledger{Runs: []LedgerRun{}}
	}
	var lg Ledger
	_ = json.Unmarshal(raw, &lg)
	if lg.Runs == nil {
		lg.Runs = []LedgerRun{}
	}
	return lg
}

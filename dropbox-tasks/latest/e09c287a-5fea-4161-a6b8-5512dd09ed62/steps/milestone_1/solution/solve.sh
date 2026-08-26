#!/usr/bin/env bash
set -euo pipefail
mkdir -p /workspace/internal/app
cat > /workspace/internal/app/app.go <<'GOEOF'
package app

import (
	"bufio"
	"compress/gzip"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"
)

const dateLayout = "2006-01-02"

type Issue struct {
	SourceFile string
	SourceLine int
	Kind       string
	Entity     string
	Detail     string
}

type Claim struct {
	ClaimID    string `json:"claim_id"`
	Product    string `json:"product"`
	LossDate   string `json:"loss_date"`
	Status     string `json:"status"`
	Reserve    int    `json:"reserve"`
	Paid       int    `json:"paid"`
	Severity   int    `json:"severity"`
	Handler    string `json:"handler"`
	County     string `json:"county"`
	Revision   int    `json:"revision"`
	AgeDays    int    `json:"age_days"`
	SourceFile string `json:"source_file"`
	SourceLine int    `json:"source_line"`
}

type Totals struct {
	OpenClaims int `json:"open_claims"`
	Reserve    int `json:"reserve"`
	Paid       int `json:"paid"`
}

type ClaimReport struct {
	AsOf       string  `json:"as_of"`
	ClaimCount int     `json:"claim_count"`
	Claims     []Claim `json:"claims"`
	Totals     Totals  `json:"totals"`
}

func Run(args []string) error {
	if len(args) == 0 {
		return errors.New("missing command")
	}
	switch args[0] {
	case "ingest":
		return runIngest(args[1:])
	default:
		return fmt.Errorf("unknown command %q", args[0])
	}
}

func runIngest(args []string) error {
	fs := flag.NewFlagSet("ingest", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	root := fs.String("claims-root", "", "")
	asOfText := fs.String("as-of", "", "")
	claimsOut := fs.String("claims-out", "", "")
	issuesOut := fs.String("issues-out", "", "")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *root == "" || *asOfText == "" || *claimsOut == "" || *issuesOut == "" {
		return errors.New("missing required flags")
	}
	report, issues, err := buildClaims(*root, *asOfText)
	if err != nil {
		return err
	}
	if err := writeJSON(*claimsOut, report); err != nil {
		return err
	}
	return writeIssues(*issuesOut, issues)
}

func buildClaims(root string, asOfText string) (ClaimReport, []Issue, error) {
	asOf, err := time.Parse(dateLayout, asOfText)
	if err != nil {
		return ClaimReport{}, nil, fmt.Errorf("invalid as-of date")
	}
	files, err := listFiles(root, []string{".claim.jsonl", ".claim.jsonl.gz"})
	if err != nil {
		return ClaimReport{}, nil, err
	}
	issues := []Issue{}
	selected := map[string]Claim{}
	for _, file := range files {
		abs, _ := filepath.Abs(file)
		rows, err := readJSONLines(file)
		if err != nil {
			issues = append(issues, Issue{abs, 0, "invalid_claim", "", err.Error()})
			continue
		}
		for _, row := range rows {
			m, err := parseJSONObject(row.Text)
			if err != nil {
				issues = append(issues, Issue{abs, row.Line, "invalid_claim", "", err.Error()})
				continue
			}
			claim, ignored, issueDetails := claimFromMap(m, abs, row.Line, asOf)
			if len(issueDetails) > 0 {
				ent := claim.ClaimID
				for _, d := range issueDetails {
					issues = append(issues, Issue{abs, row.Line, "invalid_claim", ent, d})
				}
				continue
			}
			if ignored {
				continue
			}
			old, ok := selected[claim.ClaimID]
			if !ok || betterClaim(claim, old) {
				selected[claim.ClaimID] = claim
			}
		}
	}
	claims := make([]Claim, 0, len(selected))
	totals := Totals{}
	for _, c := range selected {
		claims = append(claims, c)
		totals.OpenClaims++
		totals.Reserve += c.Reserve
		totals.Paid += c.Paid
	}
	sort.Slice(claims, func(i, j int) bool { return claims[i].ClaimID < claims[j].ClaimID })
	sortIssues(issues)
	return ClaimReport{AsOf: asOfText, ClaimCount: len(claims), Claims: claims, Totals: totals}, issues, nil
}

func claimFromMap(m map[string]any, source string, line int, asOf time.Time) (Claim, bool, []string) {
	details := []string{}
	claimID, okID := getString(m, "claim_id", "id")
	rev, okRev := getInt(m, "revision", "rev")
	product, okProduct := getString(m, "product", "line")
	lossDate, okLoss := getString(m, "loss_date", "lossOn")
	status, okStatus := getString(m, "status", "state")
	reserve, okReserve := getInt(m, "reserve")
	paid, okPaid := getInt(m, "paid")
	severity, okSeverity := getInt(m, "severity")
	handler, _ := getString(m, "handler")
	county, _ := getString(m, "county")
	if !okID || strings.TrimSpace(claimID) == "" {
		details = append(details, "claim_id")
	}
	if !okRev {
		details = append(details, "revision")
	}
	if !okProduct || strings.TrimSpace(product) == "" {
		details = append(details, "product")
	}
	if !okLoss {
		details = append(details, "loss_date")
	}
	if !okStatus {
		details = append(details, "status")
	}
	if !okReserve {
		details = append(details, "reserve")
	}
	if !okPaid {
		details = append(details, "paid")
	}
	if !okSeverity {
		details = append(details, "severity")
	}
	var loss time.Time
	if okLoss {
		parsed, err := time.Parse(dateLayout, lossDate)
		if err != nil {
			details = append(details, "loss_date")
		} else {
			loss = parsed
		}
	}
	if okReserve && reserve < 0 {
		details = append(details, "reserve")
	}
	if okPaid && paid < 0 {
		details = append(details, "paid")
	}
	if okSeverity && (severity < 1 || severity > 5) {
		details = append(details, "severity")
	}
	if okLoss && !loss.IsZero() && loss.After(asOf) {
		details = append(details, "loss_date_after_as_of")
	}
	normStatus := strings.ToLower(strings.TrimSpace(status))
	claim := Claim{ClaimID: strings.TrimSpace(claimID), Product: strings.TrimSpace(product), LossDate: lossDate, Status: normStatus, Reserve: reserve, Paid: paid, Severity: severity, Handler: handler, County: county, Revision: rev, SourceFile: source, SourceLine: line}
	if len(details) > 0 {
		return claim, false, details
	}
	claim.AgeDays = int(asOf.Sub(loss).Hours() / 24)
	ignored := normStatus == "closed" || normStatus == "cancelled" || normStatus == "canceled"
	return claim, ignored, nil
}

func betterClaim(a, b Claim) bool {
	if a.Revision != b.Revision {
		return a.Revision > b.Revision
	}
	if a.SourceFile != b.SourceFile {
		return a.SourceFile < b.SourceFile
	}
	return a.SourceLine < b.SourceLine
}

type jsonRow struct {
	Line int
	Text string
}

func readJSONLines(path string) ([]jsonRow, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var r io.Reader = f
	if strings.HasSuffix(path, ".gz") {
		gz, err := gzip.NewReader(f)
		if err != nil {
			return nil, err
		}
		defer gz.Close()
		r = gz
	}
	scanner := bufio.NewScanner(r)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	rows := []jsonRow{}
	line := 0
	for scanner.Scan() {
		line++
		text := strings.TrimSpace(scanner.Text())
		if text == "" {
			continue
		}
		rows = append(rows, jsonRow{line, text})
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return rows, nil
}

func parseJSONObject(text string) (map[string]any, error) {
	dec := json.NewDecoder(strings.NewReader(text))
	dec.UseNumber()
	var v any
	if err := dec.Decode(&v); err != nil {
		return nil, fmt.Errorf("bad_json")
	}
	m, ok := v.(map[string]any)
	if !ok {
		return nil, fmt.Errorf("not_object")
	}
	return m, nil
}

func listFiles(root string, suffixes []string) ([]string, error) {
	out := []string{}
	err := filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		for _, suffix := range suffixes {
			if strings.HasSuffix(path, suffix) {
				out = append(out, path)
				break
			}
		}
		return nil
	})
	sort.Strings(out)
	return out, err
}

func getString(m map[string]any, keys ...string) (string, bool) {
	for _, k := range keys {
		if v, ok := m[k]; ok {
			s, ok := v.(string)
			if !ok {
				return "", false
			}
			return s, true
		}
	}
	return "", false
}

func getInt(m map[string]any, keys ...string) (int, bool) {
	for _, k := range keys {
		if v, ok := m[k]; ok {
			switch t := v.(type) {
			case json.Number:
				i, err := strconv.Atoi(t.String())
				if err != nil {
					return 0, false
				}
				return i, true
			case float64:
				if t != float64(int(t)) {
					return 0, false
				}
				return int(t), true
			case int:
				return t, true
			default:
				return 0, false
			}
		}
	}
	return 0, false
}

func writeJSON(path string, v any) error {
	if err := ensureParent(path); err != nil {
		return err
	}
	data, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	return os.WriteFile(path, data, 0644)
}

func writeIssues(path string, issues []Issue) error {
	sortIssues(issues)
	rows := [][]string{{"source_file", "source_line", "kind", "entity", "detail"}}
	for _, is := range issues {
		rows = append(rows, []string{is.SourceFile, strconv.Itoa(is.SourceLine), is.Kind, is.Entity, is.Detail})
	}
	return writeTSV(path, rows)
}

func sortIssues(issues []Issue) {
	sort.Slice(issues, func(i, j int) bool {
		a, b := issues[i], issues[j]
		if a.SourceFile != b.SourceFile {
			return a.SourceFile < b.SourceFile
		}
		if a.SourceLine != b.SourceLine {
			return a.SourceLine < b.SourceLine
		}
		if a.Kind != b.Kind {
			return a.Kind < b.Kind
		}
		if a.Entity != b.Entity {
			return a.Entity < b.Entity
		}
		return a.Detail < b.Detail
	})
}

func ensureParent(path string) error {
	dir := filepath.Dir(path)
	if dir == "." || dir == "" {
		return nil
	}
	return os.MkdirAll(dir, 0755)
}

func writeTSV(path string, rows [][]string) error {
	if err := ensureParent(path); err != nil {
		return err
	}
	var b strings.Builder
	for _, row := range rows {
		for i, cell := range row {
			if i > 0 {
				b.WriteByte('\t')
			}
			b.WriteString(cell)
		}
		b.WriteByte('\n')
	}
	return os.WriteFile(path, []byte(b.String()), 0644)
}
GOEOF
gofmt -w /workspace/internal/app/app.go
cd /workspace
go test ./...

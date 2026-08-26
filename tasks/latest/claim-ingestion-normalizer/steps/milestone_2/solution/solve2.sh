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

type Signal struct {
	Code       string `json:"code"`
	Label      string `json:"label"`
	Score      int    `json:"score"`
	Strength   int    `json:"strength"`
	ObservedOn string `json:"observed_on"`
}

type IndexClaim struct {
	ClaimID    string   `json:"claim_id"`
	Product    string   `json:"product"`
	County     string   `json:"county"`
	Severity   int      `json:"severity"`
	Reserve    int      `json:"reserve"`
	Paid       int      `json:"paid"`
	AgeDays    int      `json:"age_days"`
	TotalScore int      `json:"total_score"`
	Signals    []Signal `json:"signals"`
}

type SignalIndex struct {
	AsOf           string       `json:"as_of"`
	ClaimCount     int          `json:"claim_count"`
	CandidateCount int          `json:"candidate_count"`
	Claims         []IndexClaim `json:"claims"`
}

type ScoredSignal struct {
	ClaimID       string
	SignalCode    string
	Label         string
	Score         int
	Strength      int
	ObservedOn    string
	ClaimSeverity int
	AgeDays       int
	SourceFile    string
	SourceLine    int
}

type Rule struct {
	Code       string
	BasePoints int
	AgeDays    int
	Multiplier int
	Label      string
}

func Run(args []string) error {
	if len(args) == 0 {
		return errors.New("missing command")
	}
	switch args[0] {
	case "ingest":
		return runIngest(args[1:])
	case "score":
		return runScore(args[1:])
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
func runScore(args []string) error {
	fs := flag.NewFlagSet("score", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	claimsIn := fs.String("claims-in", "", "")
	signalsRoot := fs.String("signals-root", "", "")
	rulesPath := fs.String("rules", "", "")
	signalsOut := fs.String("signals-out", "", "")
	indexOut := fs.String("index-out", "", "")
	issuesOut := fs.String("issues-out", "", "")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *claimsIn == "" || *signalsRoot == "" || *rulesPath == "" || *signalsOut == "" || *indexOut == "" || *issuesOut == "" {
		return errors.New("missing required flags")
	}
	rows, index, issues, err := buildSignals(*claimsIn, *signalsRoot, *rulesPath)
	if err != nil {
		return err
	}
	tsv := [][]string{{"claim_id", "signal_code", "label", "score", "strength", "observed_on", "claim_severity", "age_days", "source_file", "source_line"}}
	for _, r := range rows {
		tsv = append(tsv, []string{r.ClaimID, r.SignalCode, r.Label, strconv.Itoa(r.Score), strconv.Itoa(r.Strength), r.ObservedOn, strconv.Itoa(r.ClaimSeverity), strconv.Itoa(r.AgeDays), r.SourceFile, strconv.Itoa(r.SourceLine)})
	}
	if err := writeTSV(*signalsOut, tsv); err != nil {
		return err
	}
	if err := writeJSON(*indexOut, index); err != nil {
		return err
	}
	return writeIssues(*issuesOut, issues)
}

func buildSignals(claimsIn, signalsRoot, rulesPath string) ([]ScoredSignal, SignalIndex, []Issue, error) {
	data, err := os.ReadFile(claimsIn)
	if err != nil {
		return nil, SignalIndex{}, nil, err
	}
	var report ClaimReport
	if err := json.Unmarshal(data, &report); err != nil {
		return nil, SignalIndex{}, nil, err
	}
	claims := map[string]Claim{}
	for _, c := range report.Claims {
		claims[c.ClaimID] = c
	}
	rules, ruleIssues, err := readRules(rulesPath)
	if err != nil {
		return nil, SignalIndex{}, nil, err
	}
	issues := append([]Issue{}, ruleIssues...)
	files, err := listFiles(signalsRoot, []string{".signal.jsonl", ".signal.jsonl.gz"})
	if err != nil {
		return nil, SignalIndex{}, nil, err
	}
	type rawSig struct {
		claimID, code, observedOn, action, source string
		rev, strength, line                       int
	}
	selected := map[string]rawSig{}
	asOf, _ := time.Parse(dateLayout, report.AsOf)
	for _, file := range files {
		abs, _ := filepath.Abs(file)
		rows, err := readJSONLines(file)
		if err != nil {
			issues = append(issues, Issue{abs, 0, "invalid_signal", "", err.Error()})
			continue
		}
		for _, row := range rows {
			m, err := parseJSONObject(row.Text)
			if err != nil {
				issues = append(issues, Issue{abs, row.Line, "invalid_signal", "", err.Error()})
				continue
			}
			claimID, okID := getString(m, "claim_id", "id")
			code, okCode := getString(m, "signal_code", "code")
			rev, okRev := getInt(m, "revision", "rev")
			observed, okObs := getString(m, "observed_on")
			strength, okStrength := getInt(m, "strength")
			action, _ := getString(m, "action")
			if action == "" {
				action = "active"
			}
			details := []string{}
			if !okID || strings.TrimSpace(claimID) == "" {
				details = append(details, "claim_id")
			}
			if !okCode || strings.TrimSpace(code) == "" {
				details = append(details, "signal_code")
			}
			if !okRev {
				details = append(details, "revision")
			}
			if !okObs {
				details = append(details, "observed_on")
			}
			if !okStrength || strength < 1 || strength > 5 {
				details = append(details, "strength")
			}
			var observedTime time.Time
			if okObs {
				parsed, err := time.Parse(dateLayout, observed)
				if err != nil {
					details = append(details, "observed_on")
				} else {
					observedTime = parsed
				}
			}
			if !observedTime.IsZero() && !asOf.IsZero() && observedTime.After(asOf) {
				details = append(details, "observed_on_after_as_of")
			}
			entity := strings.TrimSpace(claimID)
			if len(details) > 0 {
				for _, d := range details {
					issues = append(issues, Issue{abs, row.Line, "invalid_signal", entity, d})
				}
				continue
			}
			claimID = strings.TrimSpace(claimID)
			code = strings.TrimSpace(code)
			if _, ok := claims[claimID]; !ok {
				issues = append(issues, Issue{abs, row.Line, "missing_claim", claimID, code})
				continue
			}
			if _, ok := rules[code]; !ok {
				issues = append(issues, Issue{abs, row.Line, "missing_rule", claimID, code})
				continue
			}
			sig := rawSig{claimID: claimID, code: code, observedOn: observed, action: strings.ToLower(strings.TrimSpace(action)), source: abs, rev: rev, strength: strength, line: row.Line}
			key := claimID + "\x00" + code
			old, ok := selected[key]
			if !ok || betterSignal(sig.rev, sig.source, sig.line, old.rev, old.source, old.line) {
				selected[key] = sig
			}
		}
	}
	scored := []ScoredSignal{}
	byClaim := map[string][]Signal{}
	for _, sig := range selected {
		if sig.action == "retract" {
			continue
		}
		claim := claims[sig.claimID]
		rule := rules[sig.code]
		reserveGap := (claim.Reserve - claim.Paid) / 10000
		if reserveGap < 0 {
			reserveGap = 0
		}
		ageBonus := 0
		if claim.AgeDays >= rule.AgeDays {
			ageBonus = rule.Multiplier
		}
		score := rule.BasePoints + sig.strength*2 + claim.Severity*3 + reserveGap + ageBonus
		row := ScoredSignal{ClaimID: sig.claimID, SignalCode: sig.code, Label: rule.Label, Score: score, Strength: sig.strength, ObservedOn: sig.observedOn, ClaimSeverity: claim.Severity, AgeDays: claim.AgeDays, SourceFile: sig.source, SourceLine: sig.line}
		scored = append(scored, row)
		byClaim[sig.claimID] = append(byClaim[sig.claimID], Signal{Code: sig.code, Label: rule.Label, Score: score, Strength: sig.strength, ObservedOn: sig.observedOn})
	}
	sort.Slice(scored, func(i, j int) bool {
		a, b := scored[i], scored[j]
		if a.ClaimID != b.ClaimID {
			return a.ClaimID < b.ClaimID
		}
		if a.Score != b.Score {
			return a.Score > b.Score
		}
		return a.SignalCode < b.SignalCode
	})
	indexClaims := []IndexClaim{}
	candidateCount := 0
	for claimID, sigs := range byClaim {
		sort.Slice(sigs, func(i, j int) bool {
			if sigs[i].Score != sigs[j].Score {
				return sigs[i].Score > sigs[j].Score
			}
			return sigs[i].Code < sigs[j].Code
		})
		total := 0
		for _, s := range sigs {
			total += s.Score
			candidateCount++
		}
		c := claims[claimID]
		indexClaims = append(indexClaims, IndexClaim{ClaimID: c.ClaimID, Product: c.Product, County: c.County, Severity: c.Severity, Reserve: c.Reserve, Paid: c.Paid, AgeDays: c.AgeDays, TotalScore: total, Signals: sigs})
	}
	sort.Slice(indexClaims, func(i, j int) bool {
		if indexClaims[i].TotalScore != indexClaims[j].TotalScore {
			return indexClaims[i].TotalScore > indexClaims[j].TotalScore
		}
		return indexClaims[i].ClaimID < indexClaims[j].ClaimID
	})
	sortIssues(issues)
	return scored, SignalIndex{AsOf: report.AsOf, ClaimCount: report.ClaimCount, CandidateCount: candidateCount, Claims: indexClaims}, issues, nil
}

func betterSignal(ar int, af string, al int, br int, bf string, bl int) bool {
	if ar != br {
		return ar > br
	}
	if af != bf {
		return af < bf
	}
	return al < bl
}

func readRules(path string) (map[string]Rule, []Issue, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, nil, err
	}
	defer f.Close()
	abs, _ := filepath.Abs(path)
	scanner := bufio.NewScanner(f)
	line := 0
	rules := map[string]Rule{}
	issues := []Issue{}
	for scanner.Scan() {
		line++
		text := strings.TrimRight(scanner.Text(), "\r")
		if line == 1 {
			if text != "code\tbase_points\tage_days\tmultiplier\tlabel" {
				issues = append(issues, Issue{abs, 1, "invalid_signal", "", "rules_header"})
			}
			continue
		}
		if strings.TrimSpace(text) == "" {
			continue
		}
		parts := strings.Split(text, "\t")
		if len(parts) != 5 {
			entity := ""
			if len(parts) > 0 {
				entity = parts[0]
			}
			issues = append(issues, Issue{abs, line, "invalid_signal", entity, "rules_row"})
			continue
		}
		base, e1 := strconv.Atoi(parts[1])
		age, e2 := strconv.Atoi(parts[2])
		mult, e3 := strconv.Atoi(parts[3])
		if e1 != nil || e2 != nil || e3 != nil || parts[0] == "" {
			issues = append(issues, Issue{abs, line, "invalid_signal", parts[0], "rules_row"})
			continue
		}
		rules[parts[0]] = Rule{Code: parts[0], BasePoints: base, AgeDays: age, Multiplier: mult, Label: parts[4]}
	}
	if err := scanner.Err(); err != nil {
		return nil, nil, err
	}
	return rules, issues, nil
}
GOEOF
gofmt -w /workspace/internal/app/app.go
cd /workspace
go test ./...

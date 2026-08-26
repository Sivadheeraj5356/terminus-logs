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

type Capacity struct {
	Team        string
	Products    map[string]bool
	Counties    map[string]bool
	Day1        int
	Day2        int
	RiskCeiling int
	Active      bool
	Used1       int
	Used2       int
	Assigned    []string
}

type Assignment struct {
	ClaimID     string
	Lane        string
	Status      string
	Team        string
	Day         string
	TotalScore  int
	Product     string
	County      string
	SignalCount int
}

type LaneCounts struct {
	Expedited int `json:"expedited"`
	Standard  int `json:"standard"`
	Monitor   int `json:"monitor"`
}

type TeamSummary struct {
	Team           string   `json:"team"`
	Day1Used       int      `json:"day1_used"`
	Day2Used       int      `json:"day2_used"`
	RemainingDay1  int      `json:"remaining_day1"`
	RemainingDay2  int      `json:"remaining_day2"`
	AssignedClaims []string `json:"assigned_claims"`
}

type AssignmentSummary struct {
	AssignedCount int           `json:"assigned_count"`
	BacklogCount  int           `json:"backlog_count"`
	HoldCount     int           `json:"hold_count"`
	Lanes         LaneCounts    `json:"lanes"`
	Teams         []TeamSummary `json:"teams"`
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
	case "assign":
		return runAssignAdvanced(args[1:])
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

func runAssign(args []string) error {
	fs := flag.NewFlagSet("assign", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	indexIn := fs.String("index-in", "", "")
	capacityPath := fs.String("capacity", "", "")
	assignmentsOut := fs.String("assignments-out", "", "")
	summaryOut := fs.String("summary-out", "", "")
	issuesOut := fs.String("issues-out", "", "")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *indexIn == "" || *capacityPath == "" || *assignmentsOut == "" || *summaryOut == "" || *issuesOut == "" {
		return errors.New("missing required flags")
	}
	assignments, summary, issues, err := buildAssignments(*indexIn, *capacityPath)
	if err != nil {
		return err
	}
	rows := [][]string{{"claim_id", "lane", "status", "team", "day", "total_score", "product", "county", "signal_count"}}
	for _, a := range assignments {
		rows = append(rows, []string{a.ClaimID, a.Lane, a.Status, a.Team, a.Day, strconv.Itoa(a.TotalScore), a.Product, a.County, strconv.Itoa(a.SignalCount)})
	}
	if err := writeTSV(*assignmentsOut, rows); err != nil {
		return err
	}
	if err := writeJSON(*summaryOut, summary); err != nil {
		return err
	}
	return writeIssues(*issuesOut, issues)
}

func buildAssignments(indexIn, capacityPath string) ([]Assignment, AssignmentSummary, []Issue, error) {
	data, err := os.ReadFile(indexIn)
	if err != nil {
		return nil, AssignmentSummary{}, nil, err
	}
	var index SignalIndex
	if err := json.Unmarshal(data, &index); err != nil {
		return nil, AssignmentSummary{}, nil, err
	}
	capacities, issues, err := readCapacity(capacityPath)
	if err != nil {
		return nil, AssignmentSummary{}, nil, err
	}
	claims := append([]IndexClaim{}, index.Claims...)
	sort.Slice(claims, func(i, j int) bool {
		li, lj := laneRank(claims[i].TotalScore), laneRank(claims[j].TotalScore)
		if li != lj {
			return li < lj
		}
		if claims[i].TotalScore != claims[j].TotalScore {
			return claims[i].TotalScore > claims[j].TotalScore
		}
		return claims[i].ClaimID < claims[j].ClaimID
	})
	assignments := []Assignment{}
	summary := AssignmentSummary{}
	for _, c := range claims {
		lane := laneName(c.TotalScore)
		switch lane {
		case "expedited":
			summary.Lanes.Expedited++
		case "standard":
			summary.Lanes.Standard++
		default:
			summary.Lanes.Monitor++
		}
		eligible := eligibleTeams(capacities, c)
		assignment := Assignment{ClaimID: c.ClaimID, Lane: lane, TotalScore: c.TotalScore, Product: c.Product, County: c.County, SignalCount: len(c.Signals)}
		if len(eligible) == 0 {
			assignment.Status = "hold_no_team"
			issues = append(issues, Issue{sourceForCapacity(capacityPath), 0, "no_team", c.ClaimID, c.Product + "/" + c.County})
			summary.HoldCount++
		} else if team := chooseTeam(eligible, "day1"); team != nil {
			assignment.Status = "assigned"
			assignment.Team = team.Team
			assignment.Day = "day1"
			team.Day1--
			team.Used1++
			team.Assigned = append(team.Assigned, c.ClaimID)
			summary.AssignedCount++
		} else if team := chooseTeam(eligible, "day2"); team != nil {
			assignment.Status = "assigned"
			assignment.Team = team.Team
			assignment.Day = "day2"
			team.Day2--
			team.Used2++
			team.Assigned = append(team.Assigned, c.ClaimID)
			summary.AssignedCount++
		} else {
			assignment.Status = "backlog_capacity"
			summary.BacklogCount++
		}
		assignments = append(assignments, assignment)
	}
	sort.Slice(capacities, func(i, j int) bool { return capacities[i].Team < capacities[j].Team })
	for _, c := range capacities {
		sort.Strings(c.Assigned)
		assigned := c.Assigned
		if assigned == nil {
			assigned = []string{}
		}
		summary.Teams = append(summary.Teams, TeamSummary{Team: c.Team, Day1Used: c.Used1, Day2Used: c.Used2, RemainingDay1: c.Day1, RemainingDay2: c.Day2, AssignedClaims: assigned})
	}
	sortIssues(issues)
	return assignments, summary, issues, nil
}

func sourceForCapacity(path string) string { abs, _ := filepath.Abs(path); return abs }

func laneName(score int) string {
	if score >= 80 {
		return "expedited"
	}
	if score >= 50 {
		return "standard"
	}
	return "monitor"
}
func laneRank(score int) int {
	if score >= 80 {
		return 0
	}
	if score >= 50 {
		return 1
	}
	return 2
}

func readCapacity(path string) ([]*Capacity, []Issue, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, nil, err
	}
	defer f.Close()
	abs, _ := filepath.Abs(path)
	scanner := bufio.NewScanner(f)
	line := 0
	out := []*Capacity{}
	issues := []Issue{}
	for scanner.Scan() {
		line++
		text := strings.TrimRight(scanner.Text(), "\r")
		if line == 1 {
			if text != "team\tproducts\tcounties\tday1\tday2\trisk_ceiling\tactive" {
				issues = append(issues, Issue{abs, 1, "invalid_capacity", "", "header"})
			}
			continue
		}
		if strings.TrimSpace(text) == "" {
			continue
		}
		parts := strings.Split(text, "\t")
		if len(parts) != 7 {
			issues = append(issues, Issue{abs, line, "invalid_capacity", "", "row"})
			continue
		}
		day1, e1 := strconv.Atoi(parts[3])
		day2, e2 := strconv.Atoi(parts[4])
		ceiling, e3 := strconv.Atoi(parts[5])
		active, e4 := parseBool(parts[6])
		if parts[0] == "" || e1 != nil || e2 != nil || e3 != nil || e4 != nil || day1 < 0 || day2 < 0 || ceiling < 0 {
			issues = append(issues, Issue{abs, line, "invalid_capacity", parts[0], "row"})
			continue
		}
		out = append(out, &Capacity{Team: parts[0], Products: parseSet(parts[1]), Counties: parseSet(parts[2]), Day1: day1, Day2: day2, RiskCeiling: ceiling, Active: active})
	}
	if err := scanner.Err(); err != nil {
		return nil, nil, err
	}
	return out, issues, nil
}

func parseBool(s string) (bool, error) {
	switch strings.ToLower(strings.TrimSpace(s)) {
	case "true", "yes", "1":
		return true, nil
	case "false", "no", "0":
		return false, nil
	default:
		return false, fmt.Errorf("bad bool")
	}
}

func parseSet(s string) map[string]bool {
	out := map[string]bool{}
	for _, p := range strings.Split(s, ",") {
		p = strings.TrimSpace(p)
		if p != "" {
			out[p] = true
		}
	}
	return out
}

func matchesSet(set map[string]bool, value string) bool { return set["*"] || set[value] }

func eligibleTeams(teams []*Capacity, c IndexClaim) []*Capacity {
	out := []*Capacity{}
	for _, t := range teams {
		if !t.Active {
			continue
		}
		if !matchesSet(t.Products, c.Product) || !matchesSet(t.Counties, c.County) {
			continue
		}
		if c.TotalScore > t.RiskCeiling {
			continue
		}
		out = append(out, t)
	}
	return out
}

func chooseTeam(teams []*Capacity, day string) *Capacity {
	var best *Capacity
	bestRemaining := -1
	for _, t := range teams {
		rem := t.Day1
		if day == "day2" {
			rem = t.Day2
		}
		if rem <= 0 {
			continue
		}
		if best == nil || rem > bestRemaining || (rem == bestRemaining && t.Team < best.Team) {
			best = t
			bestRemaining = rem
		}
	}
	return best
}

type TeamDayScoreLimit struct {
	Day1 int `json:"day1"`
	Day2 int `json:"day2"`
}

type PrecedenceRule struct {
	Before    string `json:"before"`
	After     string `json:"after"`
	MinDayGap int    `json:"min_day_gap"`
}

type BundleBonus struct {
	Claims  []string `json:"claims"`
	Bonus   int      `json:"bonus"`
	SameDay bool     `json:"same_day"`
}

type AssignmentPlan struct {
	MaxTotalScore      *int                         `json:"max_total_score"`
	TeamDayScoreLimits map[string]TeamDayScoreLimit `json:"team_day_score_limits"`
	TeamSignalSkills   map[string][]string          `json:"team_signal_skills"`
	ClaimWindows       map[string][]string          `json:"claim_windows"`
	BlockedSameDay     [][]string                   `json:"blocked_same_day"`
	Requires           [][]string                   `json:"requires"`
	Precedence         []PrecedenceRule             `json:"precedence"`
	SameTeamGroups     [][]string                   `json:"same_team_groups"`
	DifferentTeamPairs [][]string                   `json:"different_team_pairs"`
	BundleBonuses      []BundleBonus                `json:"bundle_bonuses"`
}

type ScheduledChoice struct {
	ClaimID string
	Team    string
	Day     string
}

type DayPlanSummary struct {
	Day           string `json:"day"`
	AssignedCount int    `json:"assigned_count"`
	ScoreUsed     int    `json:"score_used"`
}

type AdvancedTeamSummary struct {
	Team               string   `json:"team"`
	Day1Used           int      `json:"day1_used"`
	Day2Used           int      `json:"day2_used"`
	Day1ScoreUsed      int      `json:"day1_score_used"`
	Day2ScoreUsed      int      `json:"day2_score_used"`
	RemainingDay1      int      `json:"remaining_day1"`
	RemainingDay2      int      `json:"remaining_day2"`
	RemainingDay1Score int      `json:"remaining_day1_score"`
	RemainingDay2Score int      `json:"remaining_day2_score"`
	AssignedClaims     []string `json:"assigned_claims"`
}

type AdvancedAssignmentSummary struct {
	AssignedCount  int                   `json:"assigned_count"`
	BacklogCount   int                   `json:"backlog_count"`
	HoldCount      int                   `json:"hold_count"`
	PlanValue      int                   `json:"plan_value"`
	BonusValue     int                   `json:"bonus_value"`
	TotalScoreUsed int                   `json:"total_score_used"`
	Lanes          LaneCounts            `json:"lanes"`
	Days           []DayPlanSummary      `json:"days"`
	Teams          []AdvancedTeamSummary `json:"teams"`
}

type plannerCandidate struct {
	claim       IndexClaim
	staticTeams []*Capacity
	options     []ScheduledChoice
}

type plannerResult struct {
	choices    map[string]ScheduledChoice
	planValue  int
	bonusValue int
	totalScore int
	count      int
	key        string
	valid      bool
}

func runAssignAdvanced(args []string) error {
	fs := flag.NewFlagSet("assign", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	indexIn := fs.String("index-in", "", "")
	capacityPath := fs.String("capacity", "", "")
	planPath := fs.String("plan", "", "")
	assignmentsOut := fs.String("assignments-out", "", "")
	summaryOut := fs.String("summary-out", "", "")
	issuesOut := fs.String("issues-out", "", "")
	if err := fs.Parse(args); err != nil {
		return err
	}
	if *indexIn == "" || *capacityPath == "" || *planPath == "" || *assignmentsOut == "" || *summaryOut == "" || *issuesOut == "" {
		return errors.New("missing required flags")
	}
	assignments, summary, issues, err := buildAssignmentsAdvanced(*indexIn, *capacityPath, *planPath)
	if err != nil {
		return err
	}
	rows := [][]string{{"claim_id", "lane", "status", "team", "day", "total_score", "product", "county", "signal_count"}}
	for _, a := range assignments {
		rows = append(rows, []string{a.ClaimID, a.Lane, a.Status, a.Team, a.Day, strconv.Itoa(a.TotalScore), a.Product, a.County, strconv.Itoa(a.SignalCount)})
	}
	if err := writeTSV(*assignmentsOut, rows); err != nil {
		return err
	}
	if err := writeJSON(*summaryOut, summary); err != nil {
		return err
	}
	return writeIssues(*issuesOut, issues)
}

func readAssignmentPlan(path string, index SignalIndex, capacities []*Capacity) (AssignmentPlan, error) {
	f, err := os.Open(path)
	if err != nil {
		return AssignmentPlan{}, err
	}
	defer f.Close()
	dec := json.NewDecoder(f)
	dec.DisallowUnknownFields()
	var plan AssignmentPlan
	if err := dec.Decode(&plan); err != nil {
		return AssignmentPlan{}, fmt.Errorf("invalid plan: %w", err)
	}
	if dec.Decode(&struct{}{}) != io.EOF {
		return AssignmentPlan{}, errors.New("invalid plan: trailing JSON")
	}
	if plan.MaxTotalScore == nil || *plan.MaxTotalScore < 0 || plan.TeamDayScoreLimits == nil || plan.TeamSignalSkills == nil || plan.ClaimWindows == nil || plan.BlockedSameDay == nil || plan.Requires == nil || plan.Precedence == nil || plan.SameTeamGroups == nil || plan.DifferentTeamPairs == nil || plan.BundleBonuses == nil {
		return AssignmentPlan{}, errors.New("invalid plan: missing top-level field")
	}
	claims := map[string]bool{}
	for _, c := range index.Claims {
		claims[c.ClaimID] = true
	}
	teams := map[string]bool{}
	for _, t := range capacities {
		teams[t.Team] = true
		limit, ok := plan.TeamDayScoreLimits[t.Team]
		if !ok || limit.Day1 < 0 || limit.Day2 < 0 {
			return AssignmentPlan{}, fmt.Errorf("invalid plan: team score limit %s", t.Team)
		}
		skills, ok := plan.TeamSignalSkills[t.Team]
		if !ok || len(skills) == 0 {
			return AssignmentPlan{}, fmt.Errorf("invalid plan: team skills %s", t.Team)
		}
		seen := map[string]bool{}
		for _, skill := range skills {
			skill = strings.TrimSpace(skill)
			if skill == "" || seen[skill] {
				return AssignmentPlan{}, fmt.Errorf("invalid plan: team skills %s", t.Team)
			}
			seen[skill] = true
		}
	}
	for team := range plan.TeamDayScoreLimits {
		if !teams[team] {
			return AssignmentPlan{}, fmt.Errorf("invalid plan: unknown team %s", team)
		}
	}
	for team := range plan.TeamSignalSkills {
		if !teams[team] {
			return AssignmentPlan{}, fmt.Errorf("invalid plan: unknown team %s", team)
		}
	}
	for claim, days := range plan.ClaimWindows {
		if !claims[claim] || len(days) == 0 {
			return AssignmentPlan{}, fmt.Errorf("invalid plan: claim window %s", claim)
		}
		seen := map[string]bool{}
		for _, day := range days {
			if (day != "day1" && day != "day2") || seen[day] {
				return AssignmentPlan{}, fmt.Errorf("invalid plan: claim window %s", claim)
			}
			seen[day] = true
		}
	}
	validatePair := func(pair []string, label string) error {
		if len(pair) != 2 || pair[0] == pair[1] || !claims[pair[0]] || !claims[pair[1]] {
			return fmt.Errorf("invalid plan: %s", label)
		}
		return nil
	}
	for _, pair := range plan.BlockedSameDay {
		if err := validatePair(pair, "blocked_same_day"); err != nil {
			return AssignmentPlan{}, err
		}
	}
	for _, pair := range plan.Requires {
		if err := validatePair(pair, "requires"); err != nil {
			return AssignmentPlan{}, err
		}
	}
	for _, pair := range plan.DifferentTeamPairs {
		if err := validatePair(pair, "different_team_pairs"); err != nil {
			return AssignmentPlan{}, err
		}
	}
	for _, rule := range plan.Precedence {
		if !claims[rule.Before] || !claims[rule.After] || rule.Before == rule.After || rule.MinDayGap < 0 || rule.MinDayGap > 1 {
			return AssignmentPlan{}, errors.New("invalid plan: precedence")
		}
	}
	for _, group := range plan.SameTeamGroups {
		if len(group) < 2 {
			return AssignmentPlan{}, errors.New("invalid plan: same_team_groups")
		}
		seen := map[string]bool{}
		for _, claim := range group {
			if !claims[claim] || seen[claim] {
				return AssignmentPlan{}, errors.New("invalid plan: same_team_groups")
			}
			seen[claim] = true
		}
	}
	for _, bonus := range plan.BundleBonuses {
		if bonus.Bonus < 0 || len(bonus.Claims) < 2 {
			return AssignmentPlan{}, errors.New("invalid plan: bundle_bonuses")
		}
		seen := map[string]bool{}
		for _, claim := range bonus.Claims {
			if !claims[claim] || seen[claim] {
				return AssignmentPlan{}, errors.New("invalid plan: bundle_bonuses")
			}
			seen[claim] = true
		}
	}
	return plan, nil
}

func buildAssignmentsAdvanced(indexIn, capacityPath, planPath string) ([]Assignment, AdvancedAssignmentSummary, []Issue, error) {
	data, err := os.ReadFile(indexIn)
	if err != nil {
		return nil, AdvancedAssignmentSummary{}, nil, err
	}
	var index SignalIndex
	if err := json.Unmarshal(data, &index); err != nil {
		return nil, AdvancedAssignmentSummary{}, nil, err
	}
	capacities, issues, err := readCapacity(capacityPath)
	if err != nil {
		return nil, AdvancedAssignmentSummary{}, nil, err
	}
	plan, err := readAssignmentPlan(planPath, index, capacities)
	if err != nil {
		return nil, AdvancedAssignmentSummary{}, nil, err
	}
	byID := map[string]IndexClaim{}
	for _, c := range index.Claims {
		byID[c.ClaimID] = c
	}
	candidates := []plannerCandidate{}
	hold := map[string]bool{}
	for _, c := range index.Claims {
		staticTeams := []*Capacity{}
		for _, t := range capacities {
			if !t.Active || !matchesSet(t.Products, c.Product) || !matchesSet(t.Counties, c.County) || c.TotalScore > t.RiskCeiling || !teamHasSignalSkill(plan.TeamSignalSkills[t.Team], c) {
				continue
			}
			staticTeams = append(staticTeams, t)
		}
		if len(staticTeams) == 0 {
			hold[c.ClaimID] = true
			issues = append(issues, Issue{sourceForCapacity(capacityPath), 0, "no_team", c.ClaimID, c.Product + "/" + c.County})
			continue
		}
		allowed := map[string]bool{"day1": true, "day2": true}
		if days, ok := plan.ClaimWindows[c.ClaimID]; ok {
			allowed = map[string]bool{}
			for _, day := range days {
				allowed[day] = true
			}
		}
		opts := []ScheduledChoice{}
		for _, t := range staticTeams {
			limit := plan.TeamDayScoreLimits[t.Team]
			if allowed["day1"] && t.Day1 > 0 && c.TotalScore <= limit.Day1 {
				opts = append(opts, ScheduledChoice{ClaimID: c.ClaimID, Team: t.Team, Day: "day1"})
			}
			if allowed["day2"] && t.Day2 > 0 && c.TotalScore <= limit.Day2 {
				opts = append(opts, ScheduledChoice{ClaimID: c.ClaimID, Team: t.Team, Day: "day2"})
			}
		}
		sort.Slice(opts, func(i, j int) bool {
			if opts[i].Day != opts[j].Day {
				return opts[i].Day < opts[j].Day
			}
			return opts[i].Team < opts[j].Team
		})
		candidates = append(candidates, plannerCandidate{claim: c, staticTeams: staticTeams, options: opts})
	}
	sort.Slice(candidates, func(i, j int) bool { return candidates[i].claim.ClaimID < candidates[j].claim.ClaimID })
	best := plannerResult{}
	current := map[string]ScheduledChoice{}
	var search func(int)
	search = func(pos int) {
		if pos == len(candidates) {
			result, ok := evaluatePlan(current, byID, capacities, plan)
			if ok && betterPlan(result, best) {
				best = result
			}
			return
		}
		cand := candidates[pos]
		search(pos + 1)
		for _, opt := range cand.options {
			current[cand.claim.ClaimID] = opt
			search(pos + 1)
			delete(current, cand.claim.ClaimID)
		}
	}
	search(0)
	if !best.valid {
		best = plannerResult{choices: map[string]ScheduledChoice{}, valid: true}
	}
	claims := append([]IndexClaim{}, index.Claims...)
	sort.Slice(claims, func(i, j int) bool {
		li, lj := laneRank(claims[i].TotalScore), laneRank(claims[j].TotalScore)
		if li != lj {
			return li < lj
		}
		if claims[i].TotalScore != claims[j].TotalScore {
			return claims[i].TotalScore > claims[j].TotalScore
		}
		return claims[i].ClaimID < claims[j].ClaimID
	})
	summary := AdvancedAssignmentSummary{PlanValue: best.planValue, BonusValue: best.bonusValue, TotalScoreUsed: best.totalScore}
	assignments := []Assignment{}
	teamByName := map[string]*Capacity{}
	for _, t := range capacities {
		teamByName[t.Team] = t
	}
	type use struct {
		c1, c2, s1, s2 int
		claims         []string
	}
	uses := map[string]*use{}
	for _, t := range capacities {
		uses[t.Team] = &use{}
	}
	day1 := DayPlanSummary{Day: "day1"}
	day2 := DayPlanSummary{Day: "day2"}
	for _, c := range claims {
		lane := laneName(c.TotalScore)
		switch lane {
		case "expedited":
			summary.Lanes.Expedited++
		case "standard":
			summary.Lanes.Standard++
		default:
			summary.Lanes.Monitor++
		}
		a := Assignment{ClaimID: c.ClaimID, Lane: lane, TotalScore: c.TotalScore, Product: c.Product, County: c.County, SignalCount: len(c.Signals)}
		if hold[c.ClaimID] {
			a.Status = "hold_no_team"
			summary.HoldCount++
		} else if choice, ok := best.choices[c.ClaimID]; ok {
			a.Status = "assigned"
			a.Team = choice.Team
			a.Day = choice.Day
			summary.AssignedCount++
			u := uses[choice.Team]
			u.claims = append(u.claims, c.ClaimID)
			if choice.Day == "day1" {
				u.c1++
				u.s1 += c.TotalScore
				day1.AssignedCount++
				day1.ScoreUsed += c.TotalScore
			} else {
				u.c2++
				u.s2 += c.TotalScore
				day2.AssignedCount++
				day2.ScoreUsed += c.TotalScore
			}
		} else {
			a.Status = "backlog_capacity"
			summary.BacklogCount++
		}
		assignments = append(assignments, a)
	}
	summary.Days = []DayPlanSummary{day1, day2}
	sort.Slice(capacities, func(i, j int) bool { return capacities[i].Team < capacities[j].Team })
	for _, t := range capacities {
		u := uses[t.Team]
		sort.Strings(u.claims)
		claimsOut := u.claims
		if claimsOut == nil {
			claimsOut = []string{}
		}
		limit := plan.TeamDayScoreLimits[t.Team]
		summary.Teams = append(summary.Teams, AdvancedTeamSummary{Team: t.Team, Day1Used: u.c1, Day2Used: u.c2, Day1ScoreUsed: u.s1, Day2ScoreUsed: u.s2, RemainingDay1: t.Day1 - u.c1, RemainingDay2: t.Day2 - u.c2, RemainingDay1Score: limit.Day1 - u.s1, RemainingDay2Score: limit.Day2 - u.s2, AssignedClaims: claimsOut})
	}
	sortIssues(issues)
	return assignments, summary, issues, nil
}

func teamHasSignalSkill(skills []string, c IndexClaim) bool {
	if len(c.Signals) == 0 {
		return false
	}
	primary := c.Signals[0].Code
	for _, skill := range skills {
		if skill == "*" || skill == primary {
			return true
		}
	}
	return false
}

func evaluatePlan(current map[string]ScheduledChoice, claims map[string]IndexClaim, capacities []*Capacity, plan AssignmentPlan) (plannerResult, bool) {
	countUse := map[string]map[string]int{}
	scoreUse := map[string]map[string]int{}
	for _, t := range capacities {
		countUse[t.Team] = map[string]int{"day1": 0, "day2": 0}
		scoreUse[t.Team] = map[string]int{"day1": 0, "day2": 0}
	}
	total := 0
	for claimID, choice := range current {
		c, ok := claims[claimID]
		if !ok {
			return plannerResult{}, false
		}
		countUse[choice.Team][choice.Day]++
		scoreUse[choice.Team][choice.Day] += c.TotalScore
		total += c.TotalScore
	}
	if total > *plan.MaxTotalScore {
		return plannerResult{}, false
	}
	for _, t := range capacities {
		if countUse[t.Team]["day1"] > t.Day1 || countUse[t.Team]["day2"] > t.Day2 {
			return plannerResult{}, false
		}
		limit := plan.TeamDayScoreLimits[t.Team]
		if scoreUse[t.Team]["day1"] > limit.Day1 || scoreUse[t.Team]["day2"] > limit.Day2 {
			return plannerResult{}, false
		}
	}
	for _, pair := range plan.BlockedSameDay {
		a, aok := current[pair[0]]
		b, bok := current[pair[1]]
		if aok && bok && a.Day == b.Day {
			return plannerResult{}, false
		}
	}
	for _, pair := range plan.Requires {
		if _, ok := current[pair[0]]; ok {
			if _, need := current[pair[1]]; !need {
				return plannerResult{}, false
			}
		}
	}
	for _, rule := range plan.Precedence {
		after, ok := current[rule.After]
		if !ok {
			continue
		}
		before, ok := current[rule.Before]
		if !ok || dayNumber(after.Day)-dayNumber(before.Day) < rule.MinDayGap {
			return plannerResult{}, false
		}
	}
	for _, group := range plan.SameTeamGroups {
		team := ""
		for _, claim := range group {
			if choice, ok := current[claim]; ok {
				if team == "" {
					team = choice.Team
				} else if team != choice.Team {
					return plannerResult{}, false
				}
			}
		}
	}
	for _, pair := range plan.DifferentTeamPairs {
		a, aok := current[pair[0]]
		b, bok := current[pair[1]]
		if aok && bok && a.Team == b.Team {
			return plannerResult{}, false
		}
	}
	bonus := 0
	for _, rule := range plan.BundleBonuses {
		day := ""
		earned := true
		for _, claim := range rule.Claims {
			choice, ok := current[claim]
			if !ok {
				earned = false
				break
			}
			if rule.SameDay {
				if day == "" {
					day = choice.Day
				} else if day != choice.Day {
					earned = false
					break
				}
			}
		}
		if earned {
			bonus += rule.Bonus
		}
	}
	choices := map[string]ScheduledChoice{}
	ids := make([]string, 0, len(current))
	for claim, choice := range current {
		choices[claim] = choice
		ids = append(ids, claim)
	}
	sort.Strings(ids)
	parts := make([]string, 0, len(ids))
	for _, claim := range ids {
		choice := current[claim]
		parts = append(parts, claim+":"+choice.Day+":"+choice.Team)
	}
	return plannerResult{choices: choices, planValue: total + bonus, bonusValue: bonus, totalScore: total, count: len(current), key: strings.Join(parts, "|"), valid: true}, true
}

func dayNumber(day string) int {
	if day == "day1" {
		return 1
	}
	return 2
}

func betterPlan(a, b plannerResult) bool {
	if !a.valid {
		return false
	}
	if !b.valid {
		return true
	}
	if a.planValue != b.planValue {
		return a.planValue > b.planValue
	}
	if a.count != b.count {
		return a.count > b.count
	}
	if a.totalScore != b.totalScore {
		return a.totalScore < b.totalScore
	}
	return a.key < b.key
}

GOEOF
gofmt -w /workspace/internal/app/app.go
cd /workspace
go test ./...

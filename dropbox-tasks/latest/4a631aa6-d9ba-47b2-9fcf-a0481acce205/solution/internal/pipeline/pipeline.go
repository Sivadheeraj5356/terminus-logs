package pipeline

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"
)

const genesisHash = "0000000000000000000000000000000000000000000000000000000000000000"

var (
	allowedMedia = map[string]bool{"SVOD": true, "AVOD": true, "THEATRICAL": true}
	utcRe        = regexp.MustCompile(`^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$`)
)

type territoryInfo struct {
	IANA       string
	Multiplier int
}

type participant struct {
	ID           string
	Weight       int
	CatalogIndex int
}

type rawEvent struct {
	EventID       string
	WorkAlias     string
	Territory     string
	Medium        string
	CapturedAt    time.Time
	PlayCount     int
	RerunIndex    int
	Revision      int
	ManifestIndex int
	SourceLine    int
}

type survivor struct {
	WorkID          string
	Territory       string
	DayLocal        string
	Medium          string
	PlayCount       int
	GrossMicroCents int
}

type dailyRow struct {
	WorkID             string
	Territory          string
	DayLocal           string
	Medium             string
	PlayCount          int
	GrossMicroCents    int
	RecoupedMicroCents int
	NetMicroCents      int
}

type weeklyRow struct {
	WorkID             string
	Territory          string
	WeekStartLocal     string
	PlayCount          int
	GrossMicroCents    int
	RecoupedMicroCents int
	NetMicroCents      int
}

type rateConfig struct {
	Medium   map[string]int
	Brackets []bracket
}

type bracket struct {
	MaxRerunIndex int
	Multiplier    int
}

func Run(root, outDir, secret string) error {
	if secret == "" {
		secret = "residual-escrow-key"
	}
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}

	works, err := loadWorks(filepath.Join(root, "data", "works.csv"))
	if err != nil {
		return err
	}
	aliases, err := loadAliases(filepath.Join(root, "data", "aliases.csv"))
	if err != nil {
		return err
	}
	participants, err := loadParticipants(filepath.Join(root, "data", "participants.csv"))
	if err != nil {
		return err
	}
	territories, err := loadTerritories(filepath.Join(root, "config", "territory_calendar.json"))
	if err != nil {
		return err
	}
	rates, err := loadRates(filepath.Join(root, "config", "rate_tiers.toml"))
	if err != nil {
		return err
	}
	recoup, err := loadRecoup(filepath.Join(root, "config", "recoupment_caps.json"))
	if err != nil {
		return err
	}
	raw, err := loadUsage(root, territories)
	if err != nil {
		return err
	}

	survivors := dedupe(raw, works, aliases, territories, rates)
	daily := aggregateDaily(survivors)
	weekly := aggregateWeekly(daily, territories)
	escrow, err := buildEscrow(daily, participants, recoup, secret)
	if err != nil {
		return err
	}

	if err := writeDaily(filepath.Join(outDir, "residual_daily.csv"), daily); err != nil {
		return err
	}
	if err := writeWeekly(filepath.Join(outDir, "residual_weekly.csv"), weekly); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outDir, "escrow_ledger.jsonl"), []byte(escrow), 0o644)
}

func loadWorks(path string) (map[string]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	r := csv.NewReader(f)
	rows, err := r.ReadAll()
	if err != nil {
		return nil, err
	}
	out := map[string]string{}
	for i, row := range rows {
		if i == 0 {
			continue
		}
		out[row[0]] = row[2]
	}
	return out, nil
}

func loadAliases(path string) (map[string]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	r := csv.NewReader(f)
	rows, err := r.ReadAll()
	if err != nil {
		return nil, err
	}
	out := map[string]string{}
	for i, row := range rows {
		if i == 0 {
			continue
		}
		out[strings.ToLower(row[0])] = row[1]
	}
	return out, nil
}

func loadParticipants(path string) (map[string][]participant, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	r := csv.NewReader(f)
	rows, err := r.ReadAll()
	if err != nil {
		return nil, err
	}
	out := map[string][]participant{}
	for i, row := range rows {
		if i == 0 {
			continue
		}
		w, _ := strconv.Atoi(row[2])
		c, _ := strconv.Atoi(row[3])
		out[row[0]] = append(out[row[0]], participant{ID: row[1], Weight: w, CatalogIndex: c})
	}
	for k := range out {
		sort.Slice(out[k], func(i, j int) bool { return out[k][i].CatalogIndex < out[k][j].CatalogIndex })
	}
	return out, nil
}

func loadTerritories(path string) (map[string]territoryInfo, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var payload struct {
		Territories map[string]struct {
			IANA       string `json:"iana"`
			Multiplier int    `json:"multiplier"`
		} `json:"territories"`
	}
	if err := json.Unmarshal(b, &payload); err != nil {
		return nil, err
	}
	out := map[string]territoryInfo{}
	for k, v := range payload.Territories {
		out[k] = territoryInfo{IANA: v.IANA, Multiplier: v.Multiplier}
	}
	return out, nil
}

func loadRecoup(path string) (map[string]map[string]map[string]int, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var out map[string]map[string]map[string]int
	return out, json.Unmarshal(b, &out)
}

func loadRates(path string) (rateConfig, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return rateConfig{}, err
	}
	cfg := rateConfig{Medium: map[string]int{}, Brackets: []bracket{}}
	currentMedium := ""
	currentBracket := bracket{}
	inBracket := false
	for _, raw := range strings.Split(string(b), "\n") {
		line := strings.TrimSpace(raw)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if strings.HasPrefix(line, "[medium.") {
			currentMedium = strings.TrimSuffix(strings.TrimPrefix(line, "[medium."), "]")
			continue
		}
		if line == "[[rerun.brackets]]" {
			if inBracket {
				cfg.Brackets = append(cfg.Brackets, currentBracket)
			}
			currentBracket = bracket{}
			inBracket = true
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		val, _ := strconv.Atoi(strings.TrimSpace(parts[1]))
		switch key {
		case "baseRateMicroCents":
			if currentMedium != "" {
				cfg.Medium[currentMedium] = val
			}
		case "maxRerunIndex":
			currentBracket.MaxRerunIndex = val
		case "multiplier":
			currentBracket.Multiplier = val
		}
	}
	if inBracket {
		cfg.Brackets = append(cfg.Brackets, currentBracket)
	}
	sort.Slice(cfg.Brackets, func(i, j int) bool { return cfg.Brackets[i].MaxRerunIndex < cfg.Brackets[j].MaxRerunIndex })
	return cfg, nil
}

func loadUsage(root string, territories map[string]territoryInfo) ([]rawEvent, error) {
	manifestPath := filepath.Join(root, "config", "usage_ingest_order.json")
	b, err := os.ReadFile(manifestPath)
	if err != nil {
		return nil, err
	}
	var manifest struct {
		Files []string `json:"files"`
	}
	if err := json.Unmarshal(b, &manifest); err != nil {
		return nil, err
	}
	manifestIndex := map[string]int{}
	paths := []string{}
	seen := map[string]bool{}
	for i, rel := range manifest.Files {
		manifestIndex[rel] = i
		paths = append(paths, rel)
		seen[rel] = true
	}
	usageDir := filepath.Join(root, "data", "usage")
	entries, _ := os.ReadDir(usageDir)
	var extras []string
	for _, e := range entries {
		if e.IsDir() || !strings.HasSuffix(e.Name(), ".jsonl") {
			continue
		}
		rel := filepath.ToSlash(filepath.Join("data", "usage", e.Name()))
		if !seen[rel] {
			extras = append(extras, rel)
		}
	}
	sort.Strings(extras)
	for _, rel := range extras {
		manifestIndex[rel] = len(manifestIndex)
		paths = append(paths, rel)
	}

	var out []rawEvent
	for _, rel := range paths {
		full := filepath.Join(root, rel)
		content, err := os.ReadFile(full)
		if err != nil {
			return nil, err
		}
		lineNo := 0
		for _, line := range strings.Split(string(content), "\n") {
			if strings.TrimSpace(line) == "" {
				continue
			}
			lineNo++
			var obj map[string]any
			if err := json.Unmarshal([]byte(line), &obj); err != nil {
				writeAudit("bad_json", "-", rel, lineNo)
				continue
			}
			if reason := malformedReason(obj, territories); reason != "" {
				writeAudit(reason, eventID(obj), rel, lineNo)
				continue
			}
			captured, _ := parseUTCOk(stringValue(obj["capturedAt"]))
			out = append(out, rawEvent{
				EventID:       fmt.Sprint(obj["eventId"]),
				WorkAlias:     fmt.Sprint(obj["workAlias"]),
				Territory:     fmt.Sprint(obj["territory"]),
				Medium:        fmt.Sprint(obj["medium"]),
				CapturedAt:    captured,
				PlayCount:     intFrom(obj["playCount"]),
				RerunIndex:    intFrom(obj["rerunIndex"]),
				Revision:      intFrom(obj["revision"]),
				ManifestIndex: manifestIndex[rel],
				SourceLine:    lineNo,
			})
		}
	}
	return out, nil
}

func writeAudit(reason, eventID, rel string, lineNo int) {
	fmt.Fprintf(os.Stderr, "audit,%s,%s,%s,%d\n", reason, eventID, rel, lineNo)
}

func eventID(obj map[string]any) string {
	if s, ok := obj["eventId"].(string); ok && s != "" {
		return s
	}
	return "-"
}

func stringValue(v any) string {
	s, _ := v.(string)
	return s
}

func isJSONInt(v any) bool {
	switch t := v.(type) {
	case float64:
		return t == float64(int(t))
	case int:
		return true
	default:
		return false
	}
}

func malformedReason(obj map[string]any, territories map[string]territoryInfo) string {
	if stringValue(obj["eventId"]) == "" || stringValue(obj["workAlias"]) == "" {
		return "bad_id"
	}
	if _, ok := territories[stringValue(obj["territory"])]; !ok {
		return "bad_territory"
	}
	if !allowedMedia[stringValue(obj["medium"])] {
		return "bad_medium"
	}
	if _, ok := parseUTCOk(stringValue(obj["capturedAt"])); !ok {
		return "bad_time"
	}
	if !isJSONInt(obj["playCount"]) || intFrom(obj["playCount"]) < 0 {
		return "bad_play_count"
	}
	if !isJSONInt(obj["rerunIndex"]) || intFrom(obj["rerunIndex"]) < 0 {
		return "bad_rerun"
	}
	if !isJSONInt(obj["revision"]) || intFrom(obj["revision"]) < 1 {
		return "bad_revision"
	}
	return ""
}

func intFrom(v any) int {
	switch t := v.(type) {
	case float64:
		return int(t)
	case int:
		return t
	default:
		n, _ := strconv.Atoi(fmt.Sprint(v))
		return n
	}
}

func parseUTC(s string) time.Time {
	t, _ := parseUTCOk(s)
	return t
}

func parseUTCOk(s string) (time.Time, bool) {
	m := utcRe.FindStringSubmatch(s)
	if m == nil {
		return time.Time{}, false
	}
	y, _ := strconv.Atoi(m[1])
	mo, _ := strconv.Atoi(m[2])
	d, _ := strconv.Atoi(m[3])
	h, _ := strconv.Atoi(m[4])
	mi, _ := strconv.Atoi(m[5])
	sec, _ := strconv.Atoi(m[6])
	t := time.Date(y, time.Month(mo), d, h, mi, sec, 0, time.UTC)
	if t.Year() != y || int(t.Month()) != mo || t.Day() != d || t.Hour() != h || t.Minute() != mi || t.Second() != sec {
		return time.Time{}, false
	}
	return t, true
}

func loadLocation(iana string) *time.Location {
	loc, err := time.LoadLocation(iana)
	if err != nil {
		return time.UTC
	}
	return loc
}

func dayLocal(utc time.Time, iana string) string {
	loc := loadLocation(iana)
	local := localizeDST(utc, loc)
	return local.Format("2006-01-02")
}

func localizeDST(utc time.Time, loc *time.Location) time.Time {
	local := utc.In(loc)
	back := local.UTC()
	if absDuration(back.Sub(utc)) > time.Hour {
		probe := utc
		for i := 0; i < 180; i++ {
			probe = probe.Add(time.Minute)
			candidate := probe.In(loc)
			if absDuration(candidate.UTC().Sub(utc)) <= time.Minute {
				return candidate
			}
		}
	}
	return local
}

func absDuration(d time.Duration) time.Duration {
	if d < 0 {
		return -d
	}
	return d
}

func weekStart(dayLocal, iana string) string {
	loc := loadLocation(iana)
	t, err := time.ParseInLocation("2006-01-02", dayLocal, loc)
	if err != nil {
		return dayLocal
	}
	noon := time.Date(t.Year(), t.Month(), t.Day(), 12, 0, 0, 0, loc)
	monday := noon.AddDate(0, 0, -int(noon.Weekday()+6)%7)
	return monday.Format("2006-01-02")
}

func rerunMultiplier(rerun int, brackets []bracket) int {
	for _, b := range brackets {
		if rerun <= b.MaxRerunIndex {
			return b.Multiplier
		}
	}
	if len(brackets) == 0 {
		return 10000
	}
	return brackets[len(brackets)-1].Multiplier
}

func accrual(playCount, base, territoryMult, rerunMult int) int {
	num := playCount * base * territoryMult * rerunMult
	den := 10000 * 10000
	if num >= 0 {
		return num / den
	}
	return -((-num) / den)
}

func dedupe(raw []rawEvent, works map[string]string, aliases map[string]string, territories map[string]territoryInfo, rates rateConfig) []survivor {
	type key struct {
		work, terr, day, medium string
		rerun                   int
	}
	grouped := map[key][]rawEvent{}
	for _, ev := range raw {
		workID := aliases[strings.ToLower(ev.WorkAlias)]
		if workID == "" || works[workID] != "active" {
			continue
		}
		ti, ok := territories[ev.Territory]
		if !ok || !allowedMedia[ev.Medium] {
			continue
		}
		day := dayLocal(ev.CapturedAt, ti.IANA)
		k := key{workID, ev.Territory, day, ev.Medium, ev.RerunIndex}
		grouped[k] = append(grouped[k], ev)
	}

	var survivors []survivor
	for k, group := range grouped {
		sort.Slice(group, func(i, j int) bool {
			a, b := group[i], group[j]
			if a.Revision != b.Revision {
				return a.Revision > b.Revision
			}
			if a.CapturedAt.Unix() != b.CapturedAt.Unix() {
				return a.CapturedAt.After(b.CapturedAt)
			}
			if a.ManifestIndex != b.ManifestIndex {
				return a.ManifestIndex > b.ManifestIndex
			}
			return a.SourceLine > b.SourceLine
		})
		w := group[0]
		ti := territories[w.Territory]
		base := rates.Medium[w.Medium]
		rerunMult := rerunMultiplier(w.RerunIndex, rates.Brackets)
		gross := accrual(w.PlayCount, base, ti.Multiplier, rerunMult)
		survivors = append(survivors, survivor{
			WorkID: k.work, Territory: k.terr, DayLocal: k.day, Medium: k.medium,
			PlayCount: w.PlayCount, GrossMicroCents: gross,
		})
	}
	return survivors
}

func aggregateDaily(survivors []survivor) []dailyRow {
	type key struct{ work, terr, day, medium string }
	buckets := map[key]*dailyRow{}
	for _, s := range survivors {
		k := key{s.WorkID, s.Territory, s.DayLocal, s.Medium}
		row, ok := buckets[k]
		if !ok {
			row = &dailyRow{WorkID: s.WorkID, Territory: s.Territory, DayLocal: s.DayLocal, Medium: s.Medium}
			buckets[k] = row
		}
		row.PlayCount += s.PlayCount
		row.GrossMicroCents += s.GrossMicroCents
		row.NetMicroCents += s.GrossMicroCents
	}
	var rows []dailyRow
	for _, row := range buckets {
		if row.PlayCount == 0 {
			continue
		}
		rows = append(rows, *row)
	}
	sort.Slice(rows, func(i, j int) bool {
		a, b := rows[i], rows[j]
		if a.WorkID != b.WorkID {
			return a.WorkID < b.WorkID
		}
		if a.Territory != b.Territory {
			return a.Territory < b.Territory
		}
		if a.DayLocal != b.DayLocal {
			return a.DayLocal < b.DayLocal
		}
		return a.Medium < b.Medium
	})
	return rows
}

func aggregateWeekly(daily []dailyRow, territories map[string]territoryInfo) []weeklyRow {
	type key struct{ work, terr, week string }
	buckets := map[key]*weeklyRow{}
	for _, d := range daily {
		iana := territories[d.Territory].IANA
		wk := weekStart(d.DayLocal, iana)
		k := key{d.WorkID, d.Territory, wk}
		row, ok := buckets[k]
		if !ok {
			row = &weeklyRow{WorkID: d.WorkID, Territory: d.Territory, WeekStartLocal: wk}
			buckets[k] = row
		}
		row.PlayCount += d.PlayCount
		row.GrossMicroCents += d.GrossMicroCents
		row.NetMicroCents += d.NetMicroCents
	}
	var rows []weeklyRow
	for _, row := range buckets {
		rows = append(rows, *row)
	}
	sort.Slice(rows, func(i, j int) bool {
		a, b := rows[i], rows[j]
		if a.WorkID != b.WorkID {
			return a.WorkID < b.WorkID
		}
		if a.Territory != b.Territory {
			return a.Territory < b.Territory
		}
		return a.WeekStartLocal < b.WeekStartLocal
	})
	return rows
}

func applyRecoupment(gross int, caps map[string]int) int {
	remaining := gross
	total := 0
	for _, tier := range []string{"distributor", "producer", "participant"} {
		cap := caps[tier]
		take := cap
		if take > remaining {
			take = remaining
		}
		total += take
		remaining -= take
		if remaining <= 0 {
			break
		}
	}
	return gross - total
}

func splitPool(net int, parts []participant) map[string]int {
	out := map[string]int{}
	if net <= 0 || len(parts) == 0 {
		return out
	}
	totalWeight := 0
	for _, p := range parts {
		totalWeight += p.Weight
	}
	assigned := 0
	for _, p := range parts {
		share := (net * p.Weight) / totalWeight
		out[p.ID] = share
		assigned += share
	}
	remainder := net - assigned
	ordered := append([]participant{}, parts...)
	sort.Slice(ordered, func(i, j int) bool { return ordered[i].CatalogIndex < ordered[j].CatalogIndex })
	idx := 0
	for remainder > 0 {
		p := ordered[idx%len(ordered)]
		out[p.ID]++
		remainder--
		idx++
	}
	return out
}

type escrowLine struct {
	WorkID           string `json:"workId"`
	Territory        string `json:"territory"`
	PeriodMonth      string `json:"periodMonth"`
	ParticipantID    string `json:"participantId"`
	AmountMicroCents int    `json:"amountMicroCents"`
	CatalogIndex     int    `json:"catalogIndex"`
}

type escrowFooter struct {
	Type                string `json:"type"`
	PeriodMonth         string `json:"periodMonth"`
	PoolTotalMicroCents int    `json:"poolTotalMicroCents"`
	LineCount           int    `json:"lineCount"`
	PrevHash            string `json:"prevHash"`
	EntryHash           string `json:"entryHash"`
}

func buildEscrow(daily []dailyRow, participants map[string][]participant, recoup map[string]map[string]map[string]int, secret string) (string, error) {
	type groupKey struct{ work, terr, period string }
	groups := map[groupKey]int{}
	for _, d := range daily {
		period := d.DayLocal[:7]
		k := groupKey{d.WorkID, d.Territory, period}
		groups[k] += d.GrossMicroCents
	}
	if len(groups) == 0 {
		return "", nil
	}
	periodMonth := ""
	for k := range groups {
		if k.period > periodMonth {
			periodMonth = k.period
		}
	}

	var body []escrowLine
	keys := make([]groupKey, 0, len(groups))
	for k := range groups {
		if k.period == periodMonth {
			keys = append(keys, k)
		}
	}
	sort.Slice(keys, func(i, j int) bool {
		a, b := keys[i], keys[j]
		if a.work != b.work {
			return a.work < b.work
		}
		return a.terr < b.terr
	})

	for _, k := range keys {
		gross := groups[k]
		caps := map[string]int{}
		if w, ok := recoup[k.work]; ok {
			if t, ok := w[k.terr]; ok {
				caps = t
			}
		}
		net := applyRecoupment(gross, caps)
		shares := splitPool(net, participants[k.work])
		parts := participants[k.work]
		sort.Slice(parts, func(i, j int) bool { return parts[i].CatalogIndex < parts[j].CatalogIndex })
		for _, p := range parts {
			amt := shares[p.ID]
			if amt <= 0 {
				continue
			}
			body = append(body, escrowLine{
				WorkID: k.work, Territory: k.terr, PeriodMonth: k.period,
				ParticipantID: p.ID, AmountMicroCents: amt, CatalogIndex: p.CatalogIndex,
			})
		}
	}

	poolTotal := 0
	for _, line := range body {
		poolTotal += line.AmountMicroCents
	}
	msg := fmt.Sprintf("%s|%d|%d|%s", periodMonth, poolTotal, len(body), genesisHash)
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(msg))
	entryHash := hex.EncodeToString(mac.Sum(nil))
	footer := escrowFooter{
		Type: "footer", PeriodMonth: periodMonth, PoolTotalMicroCents: poolTotal,
		LineCount: len(body), PrevHash: genesisHash, EntryHash: entryHash,
	}

	var sb strings.Builder
	for _, line := range body {
		b, _ := json.Marshal(line)
		sb.Write(b)
		sb.WriteByte('\n')
	}
	fb, _ := json.Marshal(footer)
	sb.Write(fb)
	sb.WriteByte('\n')
	return sb.String(), nil
}

func writeDaily(path string, rows []dailyRow) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	w := csv.NewWriter(f)
	_ = w.Write([]string{"workId", "territory", "dayLocal", "medium", "playCount", "grossMicroCents", "recoupedMicroCents", "netMicroCents"})
	for _, row := range rows {
		_ = w.Write([]string{
			row.WorkID, row.Territory, row.DayLocal, row.Medium,
			strconv.Itoa(row.PlayCount), strconv.Itoa(row.GrossMicroCents), "0", strconv.Itoa(row.NetMicroCents),
		})
	}
	w.Flush()
	return w.Error()
}

func writeWeekly(path string, rows []weeklyRow) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	w := csv.NewWriter(f)
	_ = w.Write([]string{"workId", "territory", "weekStartLocal", "playCount", "grossMicroCents", "recoupedMicroCents", "netMicroCents"})
	for _, row := range rows {
		_ = w.Write([]string{
			row.WorkID, row.Territory, row.WeekStartLocal,
			strconv.Itoa(row.PlayCount), strconv.Itoa(row.GrossMicroCents), "0", strconv.Itoa(row.NetMicroCents),
		})
	}
	w.Flush()
	return w.Error()
}

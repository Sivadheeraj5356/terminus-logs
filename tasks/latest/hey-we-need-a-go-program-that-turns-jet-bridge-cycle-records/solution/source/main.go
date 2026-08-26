package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

type rampRow struct {
	CycleID       string  `json:"cycle_id"`
	CarrierIATA   string  `json:"carrier_iata"`
	GateZone      string  `json:"gate_zone"`
	BodyCode      string  `json:"body_code"`
	MtowTons      any     `json:"mtow_tons"`
	GateAssigned  string  `json:"gate_assigned_ts"`
	ActualInBlock string  `json:"actual_inblock_ts"`
	DwellMinutes  int     `json:"dwell_minutes"`
	Status        string  `json:"status"`
	Movement      string  `json:"movement"`
	SourceLine    int     `json:"-"`
	SourceFile    string  `json:"-"`
	mtowInt       int
	mtowIsFloat   bool
}

type tierEntry struct {
	BodyCode     string `json:"body_code"`
	EffectiveFrom string `json:"effective_from"`
	BaseCents    int    `json:"base_cents"`
	PerMinuteCents int  `json:"per_minute_cents"`
}

type tierTable struct {
	Entries []tierEntry `json:"entries"`
}

type gateZone struct {
	Code             string `json:"code"`
	MonthlyCapCents  int    `json:"monthly_cap_cents"`
	OffhoursPctBps   int    `json:"offhours_pct_bps"`
}

type gateTable struct {
	Zones []gateZone `json:"zones"`
}

type offHours struct {
	StartHHMM string
	EndHHMM   string
}

type cycleResult struct {
	CycleID      string `json:"cycle_id"`
	CarrierIATA  string `json:"carrier_iata"`
	GateZone     string `json:"gate_zone"`
	BodyCode     string `json:"body_code"`
	MtowTons     int    `json:"mtow_tons"`
	DwellMinutes int    `json:"dwell_minutes"`
	NetFeeCents  int    `json:"net_fee_cents"`
	Verdict      string `json:"verdict"`
	TierVersion  string `json:"tier_version"`
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}

func run() error {
	dataRoot := os.Getenv("AIRBRIDGE_DATA")
	if dataRoot == "" {
		dataRoot = "/app"
	}
	outDir := os.Getenv("AIRBRIDGE_OUT")
	if outDir == "" {
		outDir = "/app/output"
	}
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}

	rows, err := loadRows(dataRoot)
	if err != nil {
		return err
	}
	tiers, err := loadTiers(filepath.Join(dataRoot, "feebook", "airframe_rates.toml"))
	if err != nil {
		return err
	}
	gates, err := loadGates(filepath.Join(dataRoot, "feebook", "gate_zones.json"))
	if err != nil {
		return err
	}
	off, err := loadOffHours(filepath.Join(dataRoot, "feebook", "offhours_window.toml"))
	if err != nil {
		return err
	}

	results := process(rows, tiers, gates, off)
	if err := writeNDJSON(filepath.Join(outDir, "cycles.ndjson"), results); err != nil {
		return err
	}
	if err := writeSummary(filepath.Join(outDir, "summary.toml"), results); err != nil {
		return err
	}
	if err := writeDigest(filepath.Join(outDir, "digest.txt"), results); err != nil {
		return err
	}
	return nil
}

func loadRows(root string) ([]rampRow, error) {
	dir := filepath.Join(root, "ramplog")
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	files := []string{}
	for _, e := range entries {
		if strings.HasSuffix(e.Name(), ".ndjson") {
			files = append(files, e.Name())
		}
	}
	sort.Strings(files)
	rows := []rampRow{}
	for _, name := range files {
		path := filepath.Join(dir, name)
		f, err := os.Open(path)
		if err != nil {
			return nil, err
		}
		sc := bufio.NewScanner(f)
		sc.Buffer(make([]byte, 0, 1024*1024), 4*1024*1024)
		lineNo := 0
		for sc.Scan() {
			lineNo++
			line := strings.TrimSpace(sc.Text())
			if line == "" {
				continue
			}
			var raw map[string]any
			dec := json.NewDecoder(strings.NewReader(line))
			dec.UseNumber()
			if err := dec.Decode(&raw); err != nil {
				f.Close()
				return nil, fmt.Errorf("%s:%d %w", name, lineNo, err)
			}
			row := rampRow{SourceFile: name, SourceLine: lineNo}
			row.CycleID = asString(raw["cycle_id"])
			row.CarrierIATA = asString(raw["carrier_iata"])
			row.GateZone = asString(raw["gate_zone"])
			row.BodyCode = asString(raw["body_code"])
			row.MtowTons = raw["mtow_tons"]
			row.GateAssigned = asString(raw["gate_assigned_ts"])
			row.ActualInBlock = asString(raw["actual_inblock_ts"])
			row.DwellMinutes = asInt(raw["dwell_minutes"])
			row.Status = asString(raw["status"])
			row.Movement = asString(raw["movement"])
			row.mtowInt, row.mtowIsFloat = mtowParse(row.MtowTons)
			rows = append(rows, row)
		}
		f.Close()
		if err := sc.Err(); err != nil {
			return nil, err
		}
	}
	return rows, nil
}

func asString(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}

func asInt(v any) int {
	switch t := v.(type) {
	case float64:
		return int(t)
	case int:
		return t
	case json.Number:
		n, _ := t.Int64()
		return int(n)
	case string:
		n, _ := strconv.Atoi(t)
		return n
	}
	return 0
}

func mtowParse(v any) (int, bool) {
	switch t := v.(type) {
	case float64:
		return int(t), true
	case json.Number:
		s := t.String()
		if strings.Contains(s, ".") {
			f, _ := t.Float64()
			return int(f), true
		}
		n, _ := t.Int64()
		return int(n), false
	}
	return 0, false
}

func loadTiers(path string) (map[string][]tierEntry, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	entries, err := parseTiersToml(string(data))
	if err != nil {
		return nil, err
	}
	by := map[string][]tierEntry{}
	for _, e := range entries {
		by[e.BodyCode] = append(by[e.BodyCode], e)
	}
	for k := range by {
		sort.Slice(by[k], func(i, j int) bool { return by[k][i].EffectiveFrom < by[k][j].EffectiveFrom })
	}
	return by, nil
}

func parseTiersToml(s string) ([]tierEntry, error) {
	out := []tierEntry{}
	var cur tierEntry
	inBlock := false
	for _, raw := range strings.Split(s, "\n") {
		line := strings.TrimSpace(raw)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		if strings.HasPrefix(line, "[[entries]]") {
			if inBlock {
				out = append(out, cur)
			}
			cur = tierEntry{}
			inBlock = true
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		k := strings.TrimSpace(parts[0])
		v := strings.Trim(strings.TrimSpace(parts[1]), `"`)
		switch k {
		case "body_code":
			cur.BodyCode = v
		case "effective_from":
			cur.EffectiveFrom = v
		case "base_cents":
			n, _ := strconv.Atoi(v)
			cur.BaseCents = n
		case "per_minute_cents":
			n, _ := strconv.Atoi(v)
			cur.PerMinuteCents = n
		}
	}
	if inBlock {
		out = append(out, cur)
	}
	return out, nil
}

func loadGates(path string) (map[string]gateZone, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var gt gateTable
	if err := json.Unmarshal(data, &gt); err != nil {
		return nil, err
	}
	out := map[string]gateZone{}
	for _, z := range gt.Zones {
		out[z.Code] = z
	}
	return out, nil
}

func loadOffHours(path string) (offHours, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return offHours{}, err
	}
	o := offHours{}
	for _, raw := range strings.Split(string(data), "\n") {
		line := strings.TrimSpace(raw)
		if strings.HasPrefix(line, "start_hhmm") {
			o.StartHHMM = strings.Trim(strings.SplitN(line, "=", 2)[1], ` "`)
		}
		if strings.HasPrefix(line, "end_hhmm") {
			o.EndHHMM = strings.Trim(strings.SplitN(line, "=", 2)[1], ` "`)
		}
	}
	return o, nil
}

func tierActiveAt(entries []tierEntry, atTS string) (tierEntry, bool) {
	chosen := tierEntry{}
	found := false
	for _, e := range entries {
		if e.EffectiveFrom <= atTS {
			chosen = e
			found = true
		} else {
			break
		}
	}
	return chosen, found
}

func inOffHours(ts string, oh offHours) bool {
	if len(ts) < 19 {
		return false
	}
	hhmmss := ts[11:19]
	start := oh.StartHHMM + ":00"
	end := oh.EndHHMM + ":00"
	if start < end {
		return hhmmss > start && hhmmss <= end
	}
	return hhmmss > start || hhmmss <= end
}

func parseMonth(ts string) string {
	if len(ts) < 7 {
		return ""
	}
	return ts[:7]
}

func process(rows []rampRow, tiers map[string][]tierEntry, gates map[string]gateZone, oh offHours) []cycleResult {
	dupGroups := map[string][]rampRow{}
	for _, r := range rows {
		dupGroups[r.CycleID] = append(dupGroups[r.CycleID], r)
	}

	type resolved struct {
		row         rampRow
		mtow        int
		mtowIsFloat bool
		anchorBad   bool
		isDup       bool
	}
	resolvedMap := map[string]resolved{}
	cycleIDs := []string{}
	for id, group := range dupGroups {
		cycleIDs = append(cycleIDs, id)
		sort.SliceStable(group, func(i, j int) bool {
			if group[i].ActualInBlock != group[j].ActualInBlock {
				return group[i].ActualInBlock < group[j].ActualInBlock
			}
			if group[i].SourceFile != group[j].SourceFile {
				return group[i].SourceFile < group[j].SourceFile
			}
			return group[i].SourceLine < group[j].SourceLine
		})
		earliest := group[0]
		latest := group[len(group)-1]
		row := latest
		row.MtowTons = earliest.MtowTons
		row.mtowInt = earliest.mtowInt
		row.mtowIsFloat = earliest.mtowIsFloat
		isDup := len(group) > 1
		anchorBad := false
		if isDup {
			for _, g := range group {
				if g.mtowInt != earliest.mtowInt || g.mtowIsFloat != earliest.mtowIsFloat {
					anchorBad = true
					break
				}
			}
		}
		resolvedMap[id] = resolved{row: row, mtow: row.mtowInt, mtowIsFloat: row.mtowIsFloat, anchorBad: anchorBad, isDup: isDup}
	}
	sort.Strings(cycleIDs)

	monthlyTotal := map[string]int{}
	capBreached := map[string]bool{}

	keyOf := func(carrier, zone, month string) string { return carrier + "|" + zone + "|" + month }

	order := append([]string{}, cycleIDs...)
	sort.SliceStable(order, func(i, j int) bool {
		a := resolvedMap[order[i]].row
		b := resolvedMap[order[j]].row
		if a.ActualInBlock != b.ActualInBlock {
			return a.ActualInBlock < b.ActualInBlock
		}
		return a.CycleID < b.CycleID
	})

	results := make([]cycleResult, 0, len(order))

	for _, id := range order {
		rm := resolvedMap[id]
		row := rm.row

		res := cycleResult{
			CycleID:      row.CycleID,
			CarrierIATA:  row.CarrierIATA,
			GateZone:     row.GateZone,
			BodyCode:     row.BodyCode,
			MtowTons:     rm.mtow,
			DwellMinutes: row.DwellMinutes,
		}

		if rm.mtowIsFloat {
			res.Verdict = "REJECTED_NUMERIC"
			res.NetFeeCents = 0
			res.TierVersion = ""
			results = append(results, res)
			continue
		}
		if row.BodyCode != "NB" && row.BodyCode != "WB" && row.BodyCode != "RJ" {
			res.Verdict = "REJECTED_TIER"
			res.NetFeeCents = 0
			res.TierVersion = ""
			results = append(results, res)
			continue
		}
		if rm.isDup && rm.anchorBad {
			res.Verdict = "VOID_DUPLICATE"
			res.NetFeeCents = 0
			res.TierVersion = ""
			results = append(results, res)
			continue
		}

		assignedTier, foundAssigned := tierActiveAt(tiers[row.BodyCode], row.GateAssigned)
		inblockTier, foundInblock := tierActiveAt(tiers[row.BodyCode], row.ActualInBlock)
		if !foundAssigned || !foundInblock {
			res.Verdict = "REJECTED_TIER"
			res.NetFeeCents = 0
			res.TierVersion = ""
			results = append(results, res)
			continue
		}
		if assignedTier.EffectiveFrom != inblockTier.EffectiveFrom {
			res.Verdict = "STALE_TIER"
			res.NetFeeCents = 0
			res.TierVersion = assignedTier.EffectiveFrom
			results = append(results, res)
			continue
		}
		tier := assignedTier
		res.TierVersion = tier.EffectiveFrom
		baseFee := tier.BaseCents + tier.PerMinuteCents*row.DwellMinutes

		if row.Status == "HOLDOVER" {
			res.Verdict = "HOLDOVER_REBILL"
			res.NetFeeCents = baseFee * 2
			results = append(results, res)
			month := parseMonth(row.ActualInBlock)
			mk := keyOf(row.CarrierIATA, row.GateZone, month)
			monthlyTotal[mk] += res.NetFeeCents
			if gate, ok := gates[row.GateZone]; ok && monthlyTotal[mk] > gate.MonthlyCapCents {
				capBreached[mk] = true
			}
			continue
		}

		month := parseMonth(row.ActualInBlock)
		mk := keyOf(row.CarrierIATA, row.GateZone, month)
		if capBreached[mk] {
			res.Verdict = "CAPPED_OVERAGE"
			res.NetFeeCents = 0
			results = append(results, res)
			continue
		}

		offhoursAdd := 0
		gate, gateOK := gates[row.GateZone]
		if gateOK && inOffHours(row.ActualInBlock, oh) {
			offhoursAdd = baseFee * gate.OffhoursPctBps / 10000
			res.Verdict = "OFFHOURS_PREMIUM"
		} else {
			res.Verdict = "CLEARED"
		}
		res.NetFeeCents = baseFee + offhoursAdd
		monthlyTotal[mk] += res.NetFeeCents
		if gateOK && monthlyTotal[mk] > gate.MonthlyCapCents {
			capBreached[mk] = true
		}
		results = append(results, res)
	}

	sort.SliceStable(results, func(i, j int) bool {
		if results[i].CycleID != results[j].CycleID {
			return results[i].CycleID < results[j].CycleID
		}
		return results[i].GateZone < results[j].GateZone
	})
	return results
}

func canonicalLine(r cycleResult) string {
	return strings.Join([]string{
		r.CycleID,
		r.CarrierIATA,
		r.GateZone,
		r.BodyCode,
		strconv.Itoa(r.MtowTons),
		strconv.Itoa(r.DwellMinutes),
		strconv.Itoa(r.NetFeeCents),
		r.Verdict,
		r.TierVersion,
	}, "|")
}

func writeNDJSON(path string, results []cycleResult) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	w := bufio.NewWriter(f)
	for _, r := range results {
		b, err := json.Marshal(struct {
			CycleID      string `json:"cycle_id"`
			CarrierIATA  string `json:"carrier_iata"`
			GateZone     string `json:"gate_zone"`
			BodyCode     string `json:"body_code"`
			MtowTons     int    `json:"mtow_tons"`
			DwellMinutes int    `json:"dwell_minutes"`
			NetFeeCents  int    `json:"net_fee_cents"`
			Verdict      string `json:"verdict"`
			TierVersion  string `json:"tier_version"`
		}{r.CycleID, r.CarrierIATA, r.GateZone, r.BodyCode, r.MtowTons, r.DwellMinutes, r.NetFeeCents, r.Verdict, r.TierVersion})
		if err != nil {
			return err
		}
		if _, err := w.Write(b); err != nil {
			return err
		}
		if err := w.WriteByte('\n'); err != nil {
			return err
		}
	}
	return w.Flush()
}

func writeSummary(path string, results []cycleResult) error {
	type key struct {
		Carrier string
		Verdict string
	}
	counts := map[key]int{}
	totals := map[key]int{}
	for _, r := range results {
		k := key{r.CarrierIATA, r.Verdict}
		counts[k]++
		totals[k] += r.NetFeeCents
	}
	keys := make([]key, 0, len(counts))
	for k := range counts {
		keys = append(keys, k)
	}
	sort.Slice(keys, func(i, j int) bool {
		if keys[i].Carrier != keys[j].Carrier {
			return keys[i].Carrier < keys[j].Carrier
		}
		return keys[i].Verdict < keys[j].Verdict
	})
	var sb strings.Builder
	sb.WriteString("schema = \"airbridge_summary_v1\"\n\n")
	for _, k := range keys {
		sb.WriteString("[[totals]]\n")
		sb.WriteString(fmt.Sprintf("carrier_iata = \"%s\"\n", k.Carrier))
		sb.WriteString(fmt.Sprintf("verdict = \"%s\"\n", k.Verdict))
		sb.WriteString(fmt.Sprintf("cycle_count = %d\n", counts[k]))
		sb.WriteString(fmt.Sprintf("billed_cents = %d\n", totals[k]))
		sb.WriteString("\n")
	}
	return os.WriteFile(path, []byte(sb.String()), 0o644)
}

func writeDigest(path string, results []cycleResult) error {
	h := sha256.New()
	for _, r := range results {
		h.Write([]byte(canonicalLine(r)))
		h.Write([]byte{'\n'})
	}
	hex := hex.EncodeToString(h.Sum(nil))
	return os.WriteFile(path, []byte(hex+"\n"), 0o644)
}


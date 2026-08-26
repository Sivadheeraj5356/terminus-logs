#!/usr/bin/env bash
set -euo pipefail

export PATH=/usr/local/go/bin:/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export GOPROXY=off
export GOSUMDB=off
export GOTOOLCHAIN=local
export GOCACHE=${GOCACHE:-/opt/go-cache}

APP=/app
mkdir -p "$APP/output"
rm -f "$APP/output/report.json"

cat > "$APP/cmd/marcrec/main.go" <<'GOEOF'
package main

import (
	"bufio"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

type record struct {
	Shard       string `json:"shard"`
	RecordSeq   int    `json:"record_seq"`
	FieldSeq    int    `json:"field_seq"`
	Tag         string `json:"tag"`
	Verdict     string `json:"verdict"`
	PinConsumed bool   `json:"pin_consumed"`
}

type summaryBlock struct {
	TotalRecords     int `json:"total_records"`
	PinConsumedCount int `json:"pin_consumed_count"`
	CascadeArmsTotal int `json:"cascade_arms_total"`
}

type envelope struct {
	ReportDigest  string         `json:"report_digest"`
	SchemaVersion string         `json:"schema_version"`
	Records       []record       `json:"records"`
	ByVerdict     map[string]int `json:"by_verdict"`
	Summary       summaryBlock   `json:"summary"`
}

type digestPayload struct {
	Records   []record       `json:"records"`
	ByVerdict map[string]int `json:"by_verdict"`
	Summary   summaryBlock   `json:"summary"`
}

type rawField struct {
	Tag       string
	Indicator string
	Body      string
	IsControl bool
}

type rawRecord struct {
	Leader string
	Fields []rawField
}

var verdictEnum = []string{
	"CONTROL_FIELD_ACCEPTED",
	"DATA_FIELD_ACCEPTED",
	"LEADER_DECODED",
	"SUBFIELD_DELIMITER_MISSING",
	"TAG_OUT_OF_RANGE",
	"INDICATOR_NONBLANK_REJECTED",
	"ENCODING_PIN_RESCUED",
	"DUPLICATE_TAG_DROPPED",
	"CASCADE_QUARANTINED",
	"LEADER_BASE_ADDR_INVALID",
}

func main() {
	shelves := flag.String("shelves", "/app/shelves", "")
	_ = flag.String("codex", "/app/codex", "")
	seals := flag.String("seals", "/app/seals", "")
	_ = flag.String("catalog", "/app/catalog", "")
	out := flag.String("out", "/app/output/report.json", "")
	flag.Parse()

	pins := loadSeals(filepath.Join(*seals, "pin_keys.tsv"))

	shards := []string{"alpha", "beta", "gamma"}
	fileMap := map[string]string{
		"alpha": "catalog_alpha.mrk",
		"beta":  "catalog_beta.ndj",
		"gamma": "catalog_gamma.fwt",
	}

	var allRecs []record
	pinConsumedCount := 0
	cascadeArmsTotal := 0

	for _, shard := range shards {
		path := filepath.Join(*shelves, fileMap[shard])
		var recs []rawRecord
		switch shard {
		case "alpha":
			recs = parseAlpha(path)
		case "beta":
			recs = parseBeta(path)
		case "gamma":
			recs = parseGamma(path)
		}

		oorCount := 0
		cascadeArmed := false

		for idx, rec := range recs {
			recSeq := idx + 1

			leaderVerdict, pinUsed := classifyLeader(rec.Leader, shard, recSeq, pins)
			if pinUsed {
				pinConsumedCount++
			}
			allRecs = append(allRecs, record{
				Shard:       shard,
				RecordSeq:   recSeq,
				FieldSeq:    1,
				Tag:         "LDR",
				Verdict:     leaderVerdict,
				PinConsumed: pinUsed,
			})

			prevTag := ""
			for j, f := range rec.Fields {
				fieldSeq := j + 2

				baseVerdict := classifyField(f, prevTag)

				if cascadeArmed && (baseVerdict == "CONTROL_FIELD_ACCEPTED" || baseVerdict == "DATA_FIELD_ACCEPTED") {
					baseVerdict = "CASCADE_QUARANTINED"
					cascadeArmed = false
				}

				allRecs = append(allRecs, record{
					Shard:       shard,
					RecordSeq:   recSeq,
					FieldSeq:    fieldSeq,
					Tag:         f.Tag,
					Verdict:     baseVerdict,
					PinConsumed: false,
				})

				if baseVerdict == "TAG_OUT_OF_RANGE" {
					oorCount++
					if oorCount >= 2 && !cascadeArmed {
						cascadeArmed = true
						cascadeArmsTotal++
						oorCount = 0
					}
				}

				prevTag = f.Tag
			}
		}
	}

	byVerdict := map[string]int{}
	for _, v := range verdictEnum {
		byVerdict[v] = 0
	}
	for _, r := range allRecs {
		byVerdict[r.Verdict]++
	}

	sum := summaryBlock{
		TotalRecords:     len(allRecs),
		PinConsumedCount: pinConsumedCount,
		CascadeArmsTotal: cascadeArmsTotal,
	}

	dp := digestPayload{
		Records:   allRecs,
		ByVerdict: byVerdict,
		Summary:   sum,
	}
	digestBytes, _ := json.Marshal(&dp)
	sum256 := sha256.Sum256(digestBytes)
	digest := hex.EncodeToString(sum256[:])[:16]

	env := envelope{
		ReportDigest:  digest,
		SchemaVersion: "marc-classifier-v1",
		Records:       allRecs,
		ByVerdict:     byVerdict,
		Summary:       sum,
	}

	if err := os.MkdirAll(filepath.Dir(*out), 0o755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}

	data, err := json.MarshalIndent(&env, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := os.WriteFile(*out, append(data, '\n'), 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func loadSeals(path string) map[string]string {
	pins := map[string]string{}
	f, err := os.Open(path)
	if err != nil {
		return pins
	}
	defer f.Close()
	scanner := bufio.NewScanner(f)
	first := true
	for scanner.Scan() {
		if first {
			first = false
			continue
		}
		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			continue
		}
		parts := strings.Split(line, "\t")
		if len(parts) < 3 {
			continue
		}
		key := parts[0] + "|" + parts[1]
		pins[key] = parts[2]
	}
	return pins
}

func classifyLeader(leader, shard string, recSeq int, pins map[string]string) (string, bool) {
	if len(leader) < 24 {
		return "LEADER_BASE_ADDR_INVALID", false
	}
	baseAddr := leader[12:17]
	for _, c := range baseAddr {
		if c < '0' || c > '9' {
			return "LEADER_BASE_ADDR_INVALID", false
		}
	}
	enc := leader[9]
	if enc == 'a' || enc == ' ' {
		return "LEADER_DECODED", false
	}
	preimage := fmt.Sprintf("%s|%d", shard, recSeq)
	mac := hmac.New(sha256.New, []byte("marc-pin-v1"))
	mac.Write([]byte(preimage))
	want := hex.EncodeToString(mac.Sum(nil))[:16]
	got, ok := pins[preimage]
	if ok && got == want {
		return "ENCODING_PIN_RESCUED", true
	}
	return "LEADER_BASE_ADDR_INVALID", false
}

func classifyField(f rawField, prevTag string) string {
	if !validTag(f.Tag) {
		return "TAG_OUT_OF_RANGE"
	}
	if f.Tag == prevTag && prevTag != "" {
		return "DUPLICATE_TAG_DROPPED"
	}
	if f.IsControl {
		return "CONTROL_FIELD_ACCEPTED"
	}
	if len(f.Indicator) != 2 || !validIndicatorPair(f.Indicator) {
		return "INDICATOR_NONBLANK_REJECTED"
	}
	if !strings.Contains(f.Body, "$") {
		return "SUBFIELD_DELIMITER_MISSING"
	}
	return "DATA_FIELD_ACCEPTED"
}

func validTag(tag string) bool {
	if len(tag) != 3 {
		return false
	}
	for _, c := range tag {
		if c < '0' || c > '9' {
			return false
		}
	}
	if tag == "000" {
		return false
	}
	return true
}

func validIndicatorPair(ind string) bool {
	for i := 0; i < len(ind); i++ {
		c := ind[i]
		if c == ' ' {
			continue
		}
		if c >= '0' && c <= '9' {
			continue
		}
		if c >= 'a' && c <= 'z' {
			continue
		}
		return false
	}
	return true
}

func parseAlpha(path string) []rawRecord {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var recs []rawRecord
	var cur rawRecord
	have := false
	for _, line := range strings.Split(string(data), "\n") {
		if line == "" {
			if have {
				recs = append(recs, cur)
				cur = rawRecord{}
				have = false
			}
			continue
		}
		if !strings.HasPrefix(line, "=") {
			continue
		}
		if len(line) < 6 {
			continue
		}
		tag := line[1:4]
		body := ""
		if len(line) > 6 {
			body = line[6:]
		}
		if tag == "LDR" {
			cur.Leader = body
			have = true
			continue
		}
		isCtl := isControlTag(tag)
		f := rawField{Tag: tag, IsControl: isCtl}
		if isCtl {
			f.Body = body
		} else if len(body) >= 2 {
			f.Indicator = body[:2]
			f.Body = body[2:]
		} else {
			f.Indicator = body
		}
		cur.Fields = append(cur.Fields, f)
		have = true
	}
	if have {
		recs = append(recs, cur)
	}
	return recs
}

func parseBeta(path string) []rawRecord {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var recs []rawRecord
	for _, line := range strings.Split(string(data), "\n") {
		if strings.TrimSpace(line) == "" {
			continue
		}
		var obj struct {
			Leader string `json:"leader"`
			Fields []struct {
				Tag       string `json:"tag"`
				Value     string `json:"value"`
				Ind1      string `json:"ind1"`
				Ind2      string `json:"ind2"`
				Subfields []struct {
					Code  string `json:"code"`
					Value string `json:"value"`
				} `json:"subfields"`
			} `json:"fields"`
		}
		if err := json.Unmarshal([]byte(line), &obj); err != nil {
			continue
		}
		var rec rawRecord
		rec.Leader = obj.Leader
		for _, ff := range obj.Fields {
			if isControlTag(ff.Tag) {
				rec.Fields = append(rec.Fields, rawField{Tag: ff.Tag, IsControl: true, Body: ff.Value})
				continue
			}
			f := rawField{Tag: ff.Tag, Indicator: ff.Ind1 + ff.Ind2}
			var sb strings.Builder
			for _, s := range ff.Subfields {
				sb.WriteByte('$')
				sb.WriteString(s.Code)
				sb.WriteString(s.Value)
			}
			f.Body = sb.String()
			rec.Fields = append(rec.Fields, f)
		}
		recs = append(recs, rec)
	}
	return recs
}

func parseGamma(path string) []rawRecord {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var recs []rawRecord
	var cur rawRecord
	have := false
	for _, line := range strings.Split(string(data), "\n") {
		if line == "" {
			continue
		}
		if strings.HasPrefix(line, "ENDREC") {
			if have {
				recs = append(recs, cur)
				cur = rawRecord{}
				have = false
			}
			continue
		}
		if strings.HasPrefix(line, "LEADER:") {
			cur.Leader = strings.TrimPrefix(line, "LEADER:")
			have = true
			continue
		}
		if strings.HasPrefix(line, "TAG=") {
			parts := strings.SplitN(line, " ", 4)
			if len(parts) < 4 {
				continue
			}
			tag := strings.TrimPrefix(parts[0], "TAG=")
			body := ""
			if strings.HasPrefix(parts[3], "DATA=") {
				body = strings.TrimPrefix(parts[3], "DATA=")
			}
			isCtl := isControlTag(tag)
			f := rawField{Tag: tag, IsControl: isCtl}
			if isCtl {
				f.Body = body
			} else if len(body) >= 2 {
				f.Indicator = body[:2]
				f.Body = body[2:]
			} else {
				f.Indicator = body
			}
			cur.Fields = append(cur.Fields, f)
			have = true
		}
	}
	if have {
		recs = append(recs, cur)
	}
	return recs
}

func isControlTag(tag string) bool {
	if len(tag) != 3 {
		return false
	}
	for _, c := range tag {
		if c < '0' || c > '9' {
			return false
		}
	}
	return tag >= "001" && tag <= "009"
}
GOEOF

cd "$APP"
make build

"$APP/bin/marcrec" \
    --shelves "$APP/shelves" \
    --codex "$APP/codex" \
    --seals "$APP/seals" \
    --catalog "$APP/catalog" \
    --out "$APP/output/report.json"

echo "solve.sh complete"

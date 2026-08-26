// Package chandeck replays one recorded Chan (bi tu, 100-card) winning
// declaration and writes the byte-exact referee account.
package chandeck

import (
	"sort"
	"strconv"
	"strings"
)

var ranks = "23456789"
var suits = "vns"

var kinds = buildKinds()
var kindIndex = buildKindIndex()

func buildKinds() []string {
	out := make([]string, 0, 25)
	for _, s := range suits {
		for _, r := range ranks {
			out = append(out, string(r)+string(s))
		}
	}
	return append(out, "ci")
}

func buildKindIndex() map[string]int {
	m := make(map[string]int, len(kinds))
	for i, k := range kinds {
		m[k] = i
	}
	return m
}

var redKinds = map[string]bool{"9v": true, "9s": true, "8v": true, "8s": true, "ci": true}

var cuocDiem = map[string]int{
	"thienu": 6, "diau": 6, "thong": 3, "chi": 3, "banthu": 4,
	"tom": 4, "leo": 5, "bachdinh": 8, "tamdo": 8, "kinhtuchi": 8, "thienkhai": 5,
}

var seats = []string{"A", "B", "C", "D"}

const baseDiem = 3

func validCard(s string) bool {
	if s == "ci" {
		return true
	}
	if len(s) != 2 {
		return false
	}
	return s[0] >= '2' && s[0] <= '9' && (s[1] == 'v' || s[1] == 'n' || s[1] == 's')
}

func validInt(s string) bool {
	if s == "0" {
		return true
	}
	if s == "" || s[0] < '1' || s[0] > '9' {
		return false
	}
	for i := 1; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

func inSet(s string, options ...string) bool {
	for _, o := range options {
		if s == o {
			return true
		}
	}
	return false
}

type unit struct {
	kind  string
	cards [2]string
}

func parseUnit(text string) (unit, bool) {
	open := strings.IndexByte(text, '(')
	if open < 0 || !strings.HasSuffix(text, ")") {
		return unit{}, false
	}
	kind := text[:open]
	if kind != "chan" && kind != "ca" {
		return unit{}, false
	}
	inside := text[open+1 : len(text)-1]
	if strings.ContainsAny(inside, "()") {
		return unit{}, false
	}
	parts := strings.Split(inside, ",")
	if len(parts) != 2 {
		return unit{}, false
	}
	a, b := parts[0], parts[1]
	if !validCard(a) || !validCard(b) {
		return unit{}, false
	}
	if kind == "chan" {
		if a != b {
			return unit{}, false
		}
	} else {
		if a == "ci" || b == "ci" {
			return unit{}, false
		}
		if a[0] != b[0] || a[1] == b[1] {
			return unit{}, false
		}
	}
	return unit{kind, [2]string{a, b}}, true
}

func sortedPair(a, b string) [2]string {
	if kindIndex[a] <= kindIndex[b] {
		return [2]string{a, b}
	}
	return [2]string{b, a}
}

func unitText(u unit) string {
	p := sortedPair(u.cards[0], u.cards[1])
	return u.kind + "(" + p[0] + "," + p[1] + ")"
}

func fault(line int, reason string) string {
	return "Fault = line:" + strconv.Itoa(line) + " reason:" + reason + "\nResult = void\n"
}

func cleanLines(raw []byte) ([]string, int, bool) {
	for i, b := range raw {
		if b > 127 {
			n := 1
			for j := 0; j < i; j++ {
				if raw[j] == '\n' {
					n++
				}
			}
			return nil, n, false
		}
	}
	lines := strings.Split(string(raw), "\n")
	if len(lines) > 0 && lines[len(lines)-1] == "" {
		lines = lines[:len(lines)-1]
	}
	if len(lines) == 0 {
		return nil, 1, false
	}
	for idx, line := range lines {
		if line == "" || line != strings.Trim(line, " ") ||
			strings.Contains(line, "  ") || strings.Contains(line, "\t") ||
			strings.Contains(line, "\r") {
			return nil, idx + 1, false
		}
	}
	return lines, 0, true
}

func otherSeats(winner string) []string {
	out := make([]string, 0, 3)
	for _, s := range seats {
		if s != winner {
			out = append(out, s)
		}
	}
	return out
}

type toss struct {
	seat  string
	card  string
	round int
}

// Trace replays one Chan declaration and returns its exact referee account.
func Trace(raw []byte) string {
	lines, badLine, ok := cleanLines(raw)
	if !ok {
		return fault(badLine, "malformed")
	}
	if len(lines) < 6 {
		return fault(len(lines)+1, "malformed")
	}
	if lines[0] != "CHAN/1" {
		return fault(1, "malformed")
	}

	win := strings.Split(lines[1], " ")
	if len(win) != 5 || win[0] != "win" || !inSet(win[1], seats...) ||
		!inSet(win[2], "dealer", "nondealer") ||
		!inSet(win[3], "deal", "draw", "gate", "stock") ||
		!inSet(win[4], "fresh", "thong") {
		return fault(2, "malformed")
	}
	winner, role, source, streak := win[1], win[2], win[3], win[4]

	uuF := strings.Split(lines[2], " ")
	if len(uuF) != 2 || uuF[0] != "uu" || !validCard(uuF[1]) {
		return fault(3, "malformed")
	}
	uu := uuF[1]

	handF := strings.Split(lines[3], " ")
	if len(handF) != 20 || handF[0] != "hand" {
		return fault(4, "malformed")
	}
	hand := handF[1:]
	for _, c := range hand {
		if !validCard(c) {
			return fault(4, "malformed")
		}
	}

	layoutF := strings.Split(lines[4], " ")
	if len(layoutF) != 2 || layoutF[0] != "layout" || layoutF[1] == "" {
		return fault(5, "malformed")
	}
	unitTexts := strings.Split(layoutF[1], ";")
	units := make([]unit, 0, len(unitTexts))
	for _, t := range unitTexts {
		u, uok := parseUnit(t)
		if !uok {
			return fault(5, "malformed")
		}
		units = append(units, u)
	}

	if lines[5] != "log" {
		return fault(6, "malformed")
	}

	log := make([]toss, 0, len(lines)-6)
	for i := 6; i < len(lines); i++ {
		f := strings.Split(lines[i], " ")
		if len(f) != 4 || f[0] != "toss" || !inSet(f[1], seats...) ||
			!validCard(f[2]) || !validInt(f[3]) {
			return fault(i+1, "malformed")
		}
		r, _ := strconv.Atoi(f[3])
		log = append(log, toss{f[1], f[2], r})
	}

	// semantic validation: hand, layout, log
	full := map[string]int{}
	for _, c := range hand {
		full[c]++
	}
	full[uu]++
	for _, c := range full {
		if c > 4 {
			return fault(4, "bad-hand")
		}
	}

	if len(units) != 10 {
		return fault(5, "bad-layout")
	}
	laid := map[string]int{}
	for _, u := range units {
		laid[u.cards[0]]++
		laid[u.cards[1]]++
	}
	if !sameCounts(laid, full) {
		return fault(5, "bad-layout")
	}
	if units[0].cards[0] != uu && units[0].cards[1] != uu {
		return fault(5, "bad-layout")
	}

	prev := 0
	for i, t := range log {
		if t.round < 1 || t.round < prev {
			return fault(6+i+1, "bad-log")
		}
		prev = t.round
	}

	// winning honours
	banthu := units[0].kind == "chan" && source != "deal"
	thienu := role == "dealer" && source == "deal"
	diau := role == "nondealer" && source == "deal"
	suppress := thienu || diau

	have := map[string]int{}
	reds := 0
	for _, c := range hand {
		have[c]++
		if redKinds[c] {
			reds++
		}
	}
	have[uu]++
	if redKinds[uu] {
		reds++
	}

	chanKinds := map[string]bool{}
	for _, u := range units {
		if u.kind == "chan" {
			chanKinds[u.cards[0]] = true
		}
	}
	quadCount := 0
	for _, k := range kinds {
		if k != "ci" && have[k] == 4 {
			quadCount++
		}
	}

	var cuoc []string
	if thienu {
		cuoc = append(cuoc, "thienu")
	}
	if diau {
		cuoc = append(cuoc, "diau")
	}
	if streak == "thong" && !suppress {
		cuoc = append(cuoc, "thong")
	}
	if source == "gate" && !suppress {
		cuoc = append(cuoc, "chi")
	}
	if banthu {
		cuoc = append(cuoc, "banthu")
	}
	if have["3v"] >= 1 && have["3s"] >= 1 && have["7n"] >= 1 {
		cuoc = append(cuoc, "tom")
	}
	if have["9v"] >= 1 && have["8s"] >= 1 && have["ci"] >= 1 {
		cuoc = append(cuoc, "leo")
	}
	if reds == 0 {
		cuoc = append(cuoc, "bachdinh")
	}
	if reds == 8 {
		cuoc = append(cuoc, "tamdo")
	}
	if have["ci"] == 4 {
		cuoc = append(cuoc, "kinhtuchi")
	}
	for i := 0; i < quadCount; i++ {
		cuoc = append(cuoc, "thienkhai")
	}

	diem := baseDiem
	if len(cuoc) == 0 {
		cuoc = []string{"xuong"}
	} else {
		for _, name := range cuoc {
			diem += cuocDiem[name]
		}
	}

	// fines from the discard log
	type fine struct {
		kind, seat string
		points     int
	}
	var fines []fine
	seatPoints := map[string]int{}
	for _, seat := range otherSeats(winner) {
		var seatTosses []toss
		for _, t := range log {
			if t.seat == seat {
				seatTosses = append(seatTosses, t)
			}
		}
		for _, t := range seatTosses {
			if chanKinds[t.card] {
				fines = append(fines, fine{"treo-tranh", seat, 2})
				seatPoints[seat] += 2
			}
		}
		if source == "draw" {
			for _, t := range seatTosses {
				if t.card == uu {
					fines = append(fines, fine{"tra-cua", seat, 3})
					seatPoints[seat] += 3
				}
			}
		}
		counts := map[string]int{}
		for _, t := range seatTosses {
			counts[t.card]++
		}
		var repeated []string
		for k, c := range counts {
			if c >= 2 {
				repeated = append(repeated, k)
			}
		}
		sort.Slice(repeated, func(i, j int) bool {
			return kindIndex[repeated[i]] < kindIndex[repeated[j]]
		})
		for _, k := range repeated {
			for n := 0; n < counts[k]-1; n++ {
				fines = append(fines, fine{"lot-song", seat, 1})
				seatPoints[seat]++
			}
		}
	}
	totalFine := 0
	for _, f := range fines {
		totalFine += f.points
	}

	// render
	winning := unitText(units[0])
	rest := make([]unit, len(units)-1)
	copy(rest, units[1:])
	sort.Slice(rest, func(i, j int) bool {
		return unitLess(rest[i], rest[j])
	})
	parts := []string{winning}
	for _, u := range rest {
		parts = append(parts, unitText(u))
	}

	var out []string
	out = append(out,
		"Chan = bi-tu 100-card",
		"Winner = "+winner,
		"Source = "+role+"/"+source+"/"+streak,
		"Uu = "+uu,
		"Wait = "+waitWord(banthu),
		"Layout = "+strings.Join(parts, ";"),
		"Reds = "+strconv.Itoa(reds),
		"Cuoc = "+strings.Join(cuoc, ","),
		"Diem = "+strconv.Itoa(diem),
	)
	if len(fines) > 0 {
		for _, f := range fines {
			out = append(out, "Phat = "+f.kind+":"+f.seat+":"+strconv.Itoa(f.points))
		}
	} else {
		out = append(out, "Phat = none")
	}
	net := map[string]int{}
	for _, seat := range seats {
		net[seat] = -diem - seatPoints[seat]
	}
	net[winner] = 3*diem + totalFine
	for _, seat := range seats {
		out = append(out, "Settle "+seat+" = "+strconv.Itoa(net[seat]))
	}
	out = append(out, "Result = uu")
	return strings.Join(out, "\n") + "\n"
}

func waitWord(banthu bool) string {
	if banthu {
		return "banthu"
	}
	return "thuong"
}

func unitLess(a, b unit) bool {
	ka, kb := 1, 1
	if a.kind == "chan" {
		ka = 0
	}
	if b.kind == "chan" {
		kb = 0
	}
	if ka != kb {
		return ka < kb
	}
	pa := sortedPair(a.cards[0], a.cards[1])
	pb := sortedPair(b.cards[0], b.cards[1])
	if kindIndex[pa[0]] != kindIndex[pb[0]] {
		return kindIndex[pa[0]] < kindIndex[pb[0]]
	}
	return kindIndex[pa[1]] < kindIndex[pb[1]]
}

func sameCounts(a, b map[string]int) bool {
	if len(a) != len(b) {
		return false
	}
	for k, v := range a {
		if b[k] != v {
			return false
		}
	}
	return true
}

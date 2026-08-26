#!/bin/bash
set -euo pipefail

src="/app/environment/tools/sgfpack"
workspace="/app/workspace"
out_dir="/app/output/sgf-pack"

cat > "$src/sgf.go" <<'GO'
package main

import (
	"errors"
	"fmt"
	"os"
	"regexp"
	"strconv"
	"strings"
)

var propRE = regexp.MustCompile(`([A-Za-z_]+)\[([^\]]*)\]`)

func parseSGF(path string) (Game, error) {
	rawBytes, err := os.ReadFile(path)
	if err != nil {
		return Game{}, err
	}
	raw := strings.TrimSpace(string(rawBytes))
	if !strings.HasPrefix(raw, "(") || !strings.HasSuffix(raw, ")") {
		return Game{}, fmt.Errorf("%s is not a single SGF tree", path)
	}
	body := strings.TrimSuffix(strings.TrimPrefix(raw, "("), ")")
	pieces := strings.Split(body, ";")
	nodes := []string{}
	for _, piece := range pieces {
		piece = strings.TrimSpace(piece)
		if piece != "" {
			nodes = append(nodes, piece)
		}
	}
	if len(nodes) == 0 {
		return Game{}, fmt.Errorf("%s has no SGF nodes", path)
	}
	props := map[string]string{}
	for _, m := range propRE.FindAllStringSubmatch(nodes[0], -1) {
		props[m[1]] = m[2]
	}
	moves := []Move{}
	for _, node := range nodes[1:] {
		found := false
		for _, m := range propRE.FindAllStringSubmatch(node, -1) {
			if m[1] == "B" || m[1] == "W" {
				moves = append(moves, Move{Color: m[1], Coord: m[2]})
				found = true
				break
			}
		}
		if !found {
			return Game{}, fmt.Errorf("%s has a non-move node: %s", path, node)
		}
	}
	return Game{Props: props, Moves: moves, Raw: raw + "\n", Path: path}, nil
}

func sgfEsc(s string) string {
	s = strings.ReplaceAll(s, `\`, `\\`)
	return strings.ReplaceAll(s, "]", `\]`)
}

func buildSGF(card Card, moves []Move) string {
	props := []string{
		"GM[1]", "FF[4]", "CA[UTF-8]", "AP[sgfpack:2]", "SZ[5]",
		"RU[TTB-PSK-5]", "KM[0]", "EV[Harbor House 5x5 Cup]",
		fmt.Sprintf("RO[%d]", card.Round),
		fmt.Sprintf("ID[%s]", sgfEsc(card.GameID)),
		fmt.Sprintf("PB[%s]", sgfEsc(card.Black)),
		fmt.Sprintf("PW[%s]", sgfEsc(card.White)),
		fmt.Sprintf("RE[%s]", sgfEsc(card.Result)),
	}
	if card.Reason == "superko-forfeit" {
		props = append(props, "ADJ[superko-forfeit]", fmt.Sprintf("FP[%d]", card.OverturnedPly))
	}
	var sb strings.Builder
	sb.WriteString("(;")
	sb.WriteString(strings.Join(props, ""))
	for _, mv := range moves {
		sb.WriteString(";")
		sb.WriteString(mv.Color)
		sb.WriteString("[")
		sb.WriteString(sgfEsc(mv.Coord))
		sb.WriteString("]")
	}
	sb.WriteString(")\n")
	return sb.String()
}

func boardKey(b [boardSize][boardSize]byte) string {
	var sb strings.Builder
	for y := 0; y < boardSize; y++ {
		for x := 0; x < boardSize; x++ {
			if b[y][x] == 0 {
				sb.WriteByte('.')
			} else {
				sb.WriteByte(b[y][x])
			}
		}
	}
	return sb.String()
}

func neighbors(x, y int) [][2]int {
	out := make([][2]int, 0, 4)
	for _, d := range [][2]int{{1, 0}, {-1, 0}, {0, 1}, {0, -1}} {
		nx, ny := x+d[0], y+d[1]
		if nx >= 0 && nx < boardSize && ny >= 0 && ny < boardSize {
			out = append(out, [2]int{nx, ny})
		}
	}
	return out
}

func groupAndLibs(b [boardSize][boardSize]byte, x, y int) (map[[2]int]bool, map[[2]int]bool) {
	color := b[y][x]
	group := map[[2]int]bool{{x, y}: true}
	libs := map[[2]int]bool{}
	stack := [][2]int{{x, y}}
	for len(stack) > 0 {
		p := stack[len(stack)-1]
		stack = stack[:len(stack)-1]
		for _, n := range neighbors(p[0], p[1]) {
			v := b[n[1]][n[0]]
			if v == 0 {
				libs[n] = true
			} else if v == color && !group[n] {
				group[n] = true
				stack = append(stack, n)
			}
		}
	}
	return group, libs
}

func place(b [boardSize][boardSize]byte, color byte, coord string) ([boardSize][boardSize]byte, error) {
	if len(coord) != 2 {
		return b, fmt.Errorf("bad coordinate %q", coord)
	}
	x := int(coord[0] - 'a')
	y := int(coord[1] - 'a')
	if x < 0 || x >= boardSize || y < 0 || y >= boardSize {
		return b, fmt.Errorf("coordinate %q outside 5x5 board", coord)
	}
	if b[y][x] != 0 {
		return b, fmt.Errorf("coordinate %q is occupied", coord)
	}
	b[y][x] = color
	opp := byte('B')
	if color == 'B' {
		opp = 'W'
	}
	for _, n := range neighbors(x, y) {
		if b[n[1]][n[0]] == opp {
			grp, libs := groupAndLibs(b, n[0], n[1])
			if len(libs) == 0 {
				for p := range grp {
					b[p[1]][p[0]] = 0
				}
			}
		}
	}
	_, libs := groupAndLibs(b, x, y)
	if len(libs) == 0 {
		return b, errors.New("self-capture is not legal")
	}
	return b, nil
}

func replay(g Game) (ReplayResult, error) {
	if g.Props["SZ"] != "5" || g.Props["RU"] != "TTB-PSK-5" {
		return ReplayResult{}, errors.New("SGF must declare SZ[5] and RU[TTB-PSK-5]")
	}
	var b [boardSize][boardSize]byte
	history := map[string]bool{boardKey(b): true}
	passRun := 0
	expected := "B"
	for i, mv := range g.Moves {
		if mv.Color != expected {
			return ReplayResult{}, fmt.Errorf("ply %d has %s to move, expected %s", i+1, mv.Color, expected)
		}
		if mv.Coord == "" {
			passRun++
		} else {
			passRun = 0
			nb, err := place(b, mv.Color[0], mv.Coord)
			if err != nil {
				return ReplayResult{}, fmt.Errorf("ply %d %s[%s]: %w", i+1, mv.Color, mv.Coord, err)
			}
			key := boardKey(nb)
			if history[key] {
				return ReplayResult{}, fmt.Errorf("ply %d %s[%s] violates positional superko", i+1, mv.Color, mv.Coord)
			}
			history[key] = true
			b = nb
		}
		if expected == "B" {
			expected = "W"
		} else {
			expected = "B"
		}
	}
	bs, ws := 0, 0
	for y := 0; y < boardSize; y++ {
		for x := 0; x < boardSize; x++ {
			if b[y][x] == 'B' {
				bs++
			} else if b[y][x] == 'W' {
				ws++
			}
		}
	}
	re := g.Props["RE"]
	if strings.HasSuffix(re, "+F") {
		if g.Props["ADJ"] != "superko-forfeit" {
			return ReplayResult{}, errors.New("forfeit result must include ADJ[superko-forfeit]")
		}
		if _, err := strconv.Atoi(g.Props["FP"]); err != nil {
			return ReplayResult{}, errors.New("forfeit result must include numeric FP")
		}
		winner := strings.TrimSuffix(re, "+F")
		if winner != "B" && winner != "W" {
			return ReplayResult{}, fmt.Errorf("bad forfeit result %q", re)
		}
		bp, wp := 0, 0
		if winner == "B" {
			bp = 1
		} else {
			wp = 1
		}
		return ReplayResult{Result: re, BlackScore: bs, WhiteScore: ws, LegalPlyCount: len(g.Moves), Reason: "superko-forfeit", BlackPoints: bp, WhitePoints: wp}, nil
	}
	if len(g.Moves) < 2 || passRun < 2 {
		return ReplayResult{}, errors.New("scored games must end with two consecutive passes")
	}
	var want string
	if bs > ws {
		want = fmt.Sprintf("B+%d", bs-ws)
	} else if ws > bs {
		want = fmt.Sprintf("W+%d", ws-bs)
	} else {
		want = "0"
	}
	if re != want {
		return ReplayResult{}, fmt.Errorf("result tag %q does not match occupancy score %s", re, want)
	}
	bp, wp := 0, 0
	if strings.HasPrefix(want, "B+") {
		bp = 1
	} else if strings.HasPrefix(want, "W+") {
		wp = 1
	}
	return ReplayResult{Result: want, BlackScore: bs, WhiteScore: ws, LegalPlyCount: len(g.Moves), Reason: "score", BlackPoints: bp, WhitePoints: wp}, nil
}
GO

cat > "$src/archive.go" <<'GO'
package main

import (
	"fmt"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

func pointsForResult(result string) (int, int) {
	if strings.HasPrefix(result, "B+") {
		return 1, 0
	}
	if strings.HasPrefix(result, "W+") {
		return 0, 1
	}
	return 0, 0
}

func loadRounds(root string) ([]RoundRow, error) {
	rows, err := readTSV(filepath.Join(root, "register", "rounds.tsv"))
	if err != nil {
		return nil, err
	}
	out := []RoundRow{}
	for _, r := range rows {
		round, err := atoiField(r, "round")
		if err != nil {
			return nil, err
		}
		board, err := atoiField(r, "board")
		if err != nil {
			return nil, err
		}
		bp, err := atoiField(r, "black_points")
		if err != nil {
			return nil, err
		}
		wp, err := atoiField(r, "white_points")
		if err != nil {
			return nil, err
		}
		out = append(out, RoundRow{GameID: r["game_id"], Round: round, Board: board, Black: r["black"], White: r["white"], Record: r["record"], Result: r["result"], Reason: r["reason"], BlackPoints: bp, WhitePoints: wp})
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Round != out[j].Round {
			return out[i].Round < out[j].Round
		}
		if out[i].Board != out[j].Board {
			return out[i].Board < out[j].Board
		}
		return out[i].GameID < out[j].GameID
	})
	return out, nil
}

func loadCards(root string) (map[string]Card, error) {
	rows, err := readTSV(filepath.Join(root, "evidence", "referee", "referee_cards.tsv"))
	if err != nil {
		return nil, err
	}
	out := map[string]Card{}
	for _, r := range rows {
		round, err := atoiField(r, "round")
		if err != nil {
			return nil, err
		}
		board, err := atoiField(r, "board")
		if err != nil {
			return nil, err
		}
		ply := 0
		if strings.TrimSpace(r["overturned_ply"]) != "" {
			v, err := strconv.Atoi(r["overturned_ply"])
			if err != nil {
				return nil, fmt.Errorf("%s has bad overturned_ply=%q", r["game_id"], r["overturned_ply"])
			}
			ply = v
		}
		out[r["game_id"]] = Card{GameID: r["game_id"], Round: round, Board: board, Black: r["black"], White: r["white"], Result: r["expected_result"], Reason: r["reason"], OverturnedPly: ply, ForfeitWinner: r["forfeit_winner"]}
	}
	return out, nil
}

func loadJournal(root string) (map[string]JournalEntry, error) {
	rows, err := readTSV(filepath.Join(root, "register", "adjudication-journal.tsv"))
	if err != nil {
		return nil, err
	}
	out := map[string]JournalEntry{}
	for _, r := range rows {
		seq, err := atoiField(r, "journal_seq")
		if err != nil {
			return nil, err
		}
		entry := JournalEntry{GameID: r["game_id"], Seq: seq, Active: boolField(r, "active"), Event: r["journal_event"], Note: r["note"]}
		if !entry.Active {
			continue
		}
		if cur, ok := out[entry.GameID]; !ok || entry.Seq > cur.Seq {
			out[entry.GameID] = entry
		}
	}
	return out, nil
}

func loadCamera(root, gameID string) ([]CameraRow, error) {
	rows, err := readTSV(filepath.Join(root, "evidence", "camera", gameID+".moves"))
	if err != nil {
		return nil, err
	}
	out := []CameraRow{}
	for _, r := range rows {
		ply, err := atoiField(r, "ply")
		if err != nil {
			return nil, err
		}
		coord := r["coord"]
		if coord == "pass" {
			coord = ""
		}
		out = append(out, CameraRow{Ply: ply, Color: r["color"], Coord: coord, Status: r["status"]})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Ply < out[j].Ply })
	return out, nil
}

func officialMoves(card Card, rows []CameraRow) ([]Move, error) {
	moves := []Move{}
	seenOverturn := false
	for _, row := range rows {
		switch row.Status {
		case "played":
			if card.Reason == "superko-forfeit" && card.OverturnedPly > 0 && row.Ply >= card.OverturnedPly {
				continue
			}
			moves = append(moves, Move{Color: row.Color, Coord: row.Coord})
		case "overturned-superko":
			if card.Reason != "superko-forfeit" {
				return nil, fmt.Errorf("%s has an overturn marker but the card is %s", card.GameID, card.Reason)
			}
			if row.Ply != card.OverturnedPly {
				return nil, fmt.Errorf("%s overturn ply %d does not match card %d", card.GameID, row.Ply, card.OverturnedPly)
			}
			seenOverturn = true
		default:
			return nil, fmt.Errorf("%s has unknown camera status %q", card.GameID, row.Status)
		}
	}
	if card.Reason == "superko-forfeit" && !seenOverturn {
		return nil, fmt.Errorf("%s is missing the overturned superko marker", card.GameID)
	}
	return moves, nil
}

func validateCurrent(root string) ([]RoundRow, []Game, []ReplayResult, []string) {
	errs := []string{}
	rows, err := loadRounds(root)
	if err != nil {
		return nil, nil, nil, []string{err.Error()}
	}
	games := []Game{}
	reps := []ReplayResult{}
	seen := map[string]bool{}
	for _, row := range rows {
		if seen[row.GameID] {
			errs = append(errs, fmt.Sprintf("duplicate game_id %s", row.GameID))
		}
		seen[row.GameID] = true
		g, err := parseSGF(filepath.Join(root, row.Record))
		if err != nil {
			errs = append(errs, err.Error())
			continue
		}
		rep, replayErr := replay(g)
		if replayErr != nil {
			errs = append(errs, fmt.Sprintf("%s: %s", row.GameID, replayErr))
		}
		checks := map[string]string{"ID": row.GameID, "PB": row.Black, "PW": row.White, "RE": row.Result}
		for k, want := range checks {
			if g.Props[k] != want {
				errs = append(errs, fmt.Sprintf("%s: SGF %s=%q, register wants %q", row.GameID, k, g.Props[k], want))
			}
		}
		ro := strconv.Itoa(row.Round)
		if g.Props["RO"] != ro {
			errs = append(errs, fmt.Sprintf("%s: SGF RO=%q, register wants %q", row.GameID, g.Props["RO"], ro))
		}
		if replayErr == nil {
			if rep.Result != row.Result || rep.Reason != row.Reason || rep.BlackPoints != row.BlackPoints || rep.WhitePoints != row.WhitePoints {
				errs = append(errs, fmt.Sprintf("%s: replay result/reason/points disagree with register", row.GameID))
			}
		}
		games = append(games, g)
		reps = append(reps, rep)
	}
	return rows, games, reps, errs
}
GO

cat > "$src/repair.go" <<'GO'
package main

import (
	"fmt"
	"path/filepath"
	"sort"
)

func sortedCards(cards map[string]Card) []Card {
	var out []Card
	for _, card := range cards {
		out = append(out, card)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Round != out[j].Round {
			return out[i].Round < out[j].Round
		}
		if out[i].Board != out[j].Board {
			return out[i].Board < out[j].Board
		}
		return out[i].GameID < out[j].GameID
	})
	return out
}

func repairArchive(root string) error {
	cards, err := loadCards(root)
	if err != nil {
		return err
	}
	journal, err := loadJournal(root)
	if err != nil {
		return err
	}
	rows := []RoundRow{}
	entries := []RepairEntry{}
	for _, card := range sortedCards(cards) {
		je, ok := journal[card.GameID]
		if !ok {
			return fmt.Errorf("%s has no active adjudication journal entry", card.GameID)
		}
		cameraPath := filepath.Join(root, "evidence", "camera", card.GameID+".moves")
		cameraSHA, err := shaFile(cameraPath)
		if err != nil {
			return err
		}
		camera, err := loadCamera(root, card.GameID)
		if err != nil {
			return err
		}
		moves, err := officialMoves(card, camera)
		if err != nil {
			return err
		}
		rel := filepath.ToSlash(filepath.Join("records", "current", card.GameID+".sgf"))
		abs := filepath.Join(root, rel)
		if err := writeFileAtomic(abs, []byte(buildSGF(card, moves))); err != nil {
			return err
		}
		game, err := parseSGF(abs)
		if err != nil {
			return err
		}
		replayed, err := replay(game)
		if err != nil {
			return fmt.Errorf("%s: %w", card.GameID, err)
		}
		if replayed.Result != card.Result || replayed.Reason != card.Reason {
			return fmt.Errorf("%s: replay produced %s/%s but card requires %s/%s", card.GameID, replayed.Result, replayed.Reason, card.Result, card.Reason)
		}
		bp, wp := pointsForResult(card.Result)
		recordSHA, err := shaFile(abs)
		if err != nil {
			return err
		}
		rows = append(rows, RoundRow{GameID: card.GameID, Round: card.Round, Board: card.Board, Black: card.Black, White: card.White, Record: rel, Result: card.Result, Reason: card.Reason, BlackPoints: bp, WhitePoints: wp})
		entries = append(entries, RepairEntry{GameID: card.GameID, JournalSeq: je.Seq, JournalEvent: je.Event, CameraSHA256: cameraSHA, RecordSHA256: recordSHA, Result: card.Result, Reason: card.Reason, LegalPlyCount: replayed.LegalPlyCount})
	}
	if err := writeRounds(filepath.Join(root, "register", "rounds.tsv"), rows); err != nil {
		return err
	}
	return writeRepairState(root, entries)
}
GO

cat > "$src/audit.go" <<'GO'
package main

import (
	"fmt"
	"path/filepath"
)

func sameMoves(a, b []Move) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func auditArchive(root string) []string {
	rows, games, reps, errs := validateCurrent(root)
	if len(errs) > 0 {
		return errs
	}
	cards, err := loadCards(root)
	if err != nil {
		return []string{err.Error()}
	}
	journal, err := loadJournal(root)
	if err != nil {
		return []string{err.Error()}
	}
	stateRows, err := loadRepairState(root)
	if err != nil {
		return []string{err.Error()}
	}
	state := map[string]RepairEntry{}
	lastID := ""
	for i, entry := range stateRows {
		if i > 0 && entry.GameID <= lastID {
			errs = append(errs, "repair_state.json is not sorted by game_id")
		}
		lastID = entry.GameID
		if _, exists := state[entry.GameID]; exists {
			errs = append(errs, fmt.Sprintf("%s: duplicate repair state entry", entry.GameID))
		}
		state[entry.GameID] = entry
	}
	if len(state) != len(rows) {
		errs = append(errs, fmt.Sprintf("repair state has %d entries for %d register rows", len(state), len(rows)))
	}
	for i, row := range rows {
		card, ok := cards[row.GameID]
		if !ok {
			errs = append(errs, fmt.Sprintf("%s: missing referee card", row.GameID))
			continue
		}
		if row.Round != card.Round || row.Board != card.Board || row.Black != card.Black || row.White != card.White || row.Result != card.Result || row.Reason != card.Reason {
			errs = append(errs, fmt.Sprintf("%s: register disagrees with referee card", row.GameID))
		}
		if row.Record != filepath.ToSlash(filepath.Join("records", "current", row.GameID+".sgf")) {
			errs = append(errs, fmt.Sprintf("%s: register record path is %s", row.GameID, row.Record))
		}
		camera, err := loadCamera(root, row.GameID)
		if err != nil {
			errs = append(errs, err.Error())
			continue
		}
		wantMoves, err := officialMoves(card, camera)
		if err != nil {
			errs = append(errs, err.Error())
			continue
		}
		if !sameMoves(games[i].Moves, wantMoves) {
			errs = append(errs, fmt.Sprintf("%s: SGF moves do not match official camera sequence", row.GameID))
		}
		entry, ok := state[row.GameID]
		if !ok {
			errs = append(errs, fmt.Sprintf("%s: missing repair state entry", row.GameID))
			continue
		}
		je, ok := journal[row.GameID]
		if !ok {
			errs = append(errs, fmt.Sprintf("%s: missing active journal entry", row.GameID))
			continue
		}
		cameraSHA, err := shaFile(filepath.Join(root, "evidence", "camera", row.GameID+".moves"))
		if err != nil {
			errs = append(errs, err.Error())
			continue
		}
		recordSHA, err := shaFile(filepath.Join(root, row.Record))
		if err != nil {
			errs = append(errs, err.Error())
			continue
		}
		rep := reps[i]
		if entry.JournalSeq != je.Seq || entry.JournalEvent != je.Event || entry.CameraSHA256 != cameraSHA || entry.RecordSHA256 != recordSHA || entry.Result != row.Result || entry.Reason != row.Reason || entry.LegalPlyCount != rep.LegalPlyCount {
			errs = append(errs, fmt.Sprintf("%s: repair state is stale", row.GameID))
		}
	}
	return errs
}
GO

cat > "$src/export.go" <<'GO'
package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func standings(rows []RoundRow, reps []ReplayResult) []Standing {
	table := map[string]*Standing{}
	opponents := map[string][]string{}
	defeated := map[string][]string{}
	ensure := func(p string) *Standing {
		if table[p] == nil {
			table[p] = &Standing{Player: p}
		}
		return table[p]
	}
	for i, row := range rows {
		rep := reps[i]
		b := ensure(row.Black)
		w := ensure(row.White)
		opponents[row.Black] = append(opponents[row.Black], row.White)
		opponents[row.White] = append(opponents[row.White], row.Black)
		margin := rep.BlackScore - rep.WhiteScore
		if strings.HasPrefix(row.Result, "B+") {
			b.Wins++
			w.Losses++
			defeated[row.Black] = append(defeated[row.Black], row.White)
			b.StoneMargin += margin
			w.StoneMargin -= margin
		} else if strings.HasPrefix(row.Result, "W+") {
			w.Wins++
			b.Losses++
			defeated[row.White] = append(defeated[row.White], row.Black)
			w.StoneMargin -= margin
			b.StoneMargin += margin
		}
	}
	for p, st := range table {
		for _, opp := range opponents[p] {
			st.SOS += table[opp].Wins
		}
		for _, opp := range defeated[p] {
			st.SODOS += table[opp].Wins
		}
	}
	vals := []Standing{}
	for _, st := range table {
		vals = append(vals, *st)
	}
	sort.Slice(vals, func(i, j int) bool {
		a, b := vals[i], vals[j]
		if a.Wins != b.Wins {
			return a.Wins > b.Wins
		}
		if a.SOS != b.SOS {
			return a.SOS > b.SOS
		}
		if a.SODOS != b.SODOS {
			return a.SODOS > b.SODOS
		}
		return a.Player < b.Player
	})
	return vals
}

func exportPack(root, out string) error {
	if errs := auditArchive(root); len(errs) > 0 {
		return errors.New(strings.Join(errs, "\n"))
	}
	rows, _, reps, errs := validateCurrent(root)
	if len(errs) > 0 {
		return errors.New(strings.Join(errs, "\n"))
	}
	if err := os.RemoveAll(out); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Join(out, "records"), 0755); err != nil {
		return err
	}
	adjs := []AdjOut{}
	for i, row := range rows {
		src := filepath.Join(root, row.Record)
		dst := filepath.Join(out, "records", row.GameID+".sgf")
		raw, err := os.ReadFile(src)
		if err != nil {
			return err
		}
		if err := os.WriteFile(dst, raw, 0644); err != nil {
			return err
		}
		sh, err := shaFile(src)
		if err != nil {
			return err
		}
		rep := reps[i]
		adjs = append(adjs, AdjOut{GameID: row.GameID, Round: row.Round, Board: row.Board, Black: row.Black, White: row.White, Result: row.Result, Reason: row.Reason, BlackPoints: row.BlackPoints, WhitePoints: row.WhitePoints, BlackScore: rep.BlackScore, WhiteScore: rep.WhiteScore, LegalPlyCount: rep.LegalPlyCount, RecordSHA256: sh})
	}
	adjBytes, _ := json.MarshalIndent(adjs, "", "  ")
	if err := os.WriteFile(filepath.Join(out, "adjudications.json"), append(adjBytes, '\n'), 0644); err != nil {
		return err
	}
	var sb strings.Builder
	sb.WriteString("rank\tplayer\twins\tlosses\tsos\tsodos\tstone_margin\n")
	for i, st := range standings(rows, reps) {
		sb.WriteString(fmt.Sprintf("%d\t%s\t%d\t%d\t%d\t%d\t%d\n", i+1, st.Player, st.Wins, st.Losses, st.SOS, st.SODOS, st.StoneMargin))
	}
	if err := os.WriteFile(filepath.Join(out, "standings.tsv"), []byte(sb.String()), 0644); err != nil {
		return err
	}
	ledgerSha, err := shaFile(filepath.Join(root, "register", "rounds.tsv"))
	if err != nil {
		return err
	}
	stateSha, err := shaFile(statePath(root))
	if err != nil {
		return err
	}
	man := Manifest{Ruleset: "TTB-PSK-5", BoardSize: boardSize, RecordCount: len(rows), SourceRoundsSHA: ledgerSha, RepairStateSHA256: stateSha, Records: adjs}
	manBytes, _ := json.MarshalIndent(man, "", "  ")
	if err := os.WriteFile(filepath.Join(out, "manifest.json"), append(manBytes, '\n'), 0644); err != nil {
		return err
	}
	return nil
}
GO

cd "$src"
gofmt -w *.go
go test ./...
go build -o /app/bin/sgfpack .
/app/bin/sgfpack repair --root "$workspace"
/app/bin/sgfpack audit --root "$workspace"
rm -rf "$out_dir"
/app/bin/sgfpack export --root "$workspace" --out "$out_dir"

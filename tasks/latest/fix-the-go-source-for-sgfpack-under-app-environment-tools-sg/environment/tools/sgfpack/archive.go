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
		if _, ok := out[entry.GameID]; !ok {
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
	for _, row := range rows {
		switch row.Status {
		case "played":
			moves = append(moves, Move{Color: row.Color, Coord: row.Coord})
		case "overturned-superko":
			if card.Reason != "superko-forfeit" {
				return nil, fmt.Errorf("%s has an overturn marker but the card is %s", card.GameID, card.Reason)
			}
		default:
			return nil, fmt.Errorf("%s has unknown camera status %q", card.GameID, row.Status)
		}
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

package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func standings(rows []RoundRow, reps []ReplayResult) []Standing {
	table := map[string]*Standing{}
	ensure := func(p string) *Standing {
		if table[p] == nil {
			table[p] = &Standing{Player: p}
		}
		return table[p]
	}
	for i, row := range rows {
		_ = reps[i]
		b := ensure(row.Black)
		w := ensure(row.White)
		if strings.HasPrefix(row.Result, "B+") {
			b.Wins++
			w.Losses++
		} else if strings.HasPrefix(row.Result, "W+") {
			w.Wins++
			b.Losses++
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
		return a.Player < b.Player
	})
	return vals
}

func exportPack(root, out string) error {
	rows, _, reps, errs := validateCurrent(root)
	if len(errs) > 0 {
		return fmt.Errorf(strings.Join(errs, "\n"))
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
	man := Manifest{Ruleset: "TTB-PSK-5", BoardSize: boardSize, RecordCount: len(rows), SourceRoundsSHA: ledgerSha, Records: adjs}
	manBytes, _ := json.MarshalIndent(man, "", "  ")
	if err := os.WriteFile(filepath.Join(out, "manifest.json"), append(manBytes, '\n'), 0644); err != nil {
		return err
	}
	return nil
}

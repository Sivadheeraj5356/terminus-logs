package compile

import (
	"bufio"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"arctl.local/arctl/model"
)

func LoadPieces(root string) []model.Piece {
	base := filepath.Join(model.EnvRoot, "fixtures", root)
	var out []model.Piece
	tiers, err := os.ReadDir(base)
	if err != nil {
		return out
	}
	for _, tierDir := range tiers {
		if !tierDir.IsDir() {
			continue
		}
		tier := tierDir.Name()
		files, err := os.ReadDir(filepath.Join(base, tier))
		if err != nil {
			continue
		}
		for _, file := range files {
			if file.IsDir() {
				continue
			}
			path := filepath.Join(base, tier, file.Name())
			rows, err := parseFile(path, tier, file.Name())
			if err != nil {
				continue
			}
			out = append(out, rows...)
		}
	}
	return out
}

func parseFile(path, tier, name string) ([]model.Piece, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var out []model.Piece
	scanner := bufio.NewScanner(f)
	idx := 0
	for scanner.Scan() {
		idx++
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		out = append(out, model.Piece{Tier: tier, Src: name, Line: idx, Op: "set"})
		switch {
		case strings.HasSuffix(line, "!"):
			out[len(out)-1].Kind = strings.TrimSpace(strings.TrimSuffix(line, "!"))
			out[len(out)-1].Op = "delete"
		case strings.Contains(line, "+="):
			parts := strings.SplitN(line, "+=", 2)
			out[len(out)-1].Kind = strings.TrimSpace(parts[0])
			out[len(out)-1].Body = strings.TrimSpace(parts[1])
			out[len(out)-1].Op = "append"
		case strings.Contains(line, "-="):
			parts := strings.SplitN(line, "-=", 2)
			out[len(out)-1].Kind = strings.TrimSpace(parts[0])
			out[len(out)-1].Body = strings.TrimSpace(parts[1])
			out[len(out)-1].Op = "remove"
		default:
			parts := strings.SplitN(line, "=", 2)
			if len(parts) != 2 {
				out = out[:len(out)-1]
				continue
			}
			out[len(out)-1].Kind = strings.TrimSpace(parts[0])
			out[len(out)-1].Body = strings.TrimSpace(parts[1])
		}
	}
	return out, scanner.Err()
}

func merge_inputs(items []model.Piece, ctx model.Context) []model.Bundle {
	byKind := map[string]model.Piece{}
	for _, row := range items {
		current, ok := byKind[row.Kind]
		if !ok || row.Tier > current.Tier {
			byKind[row.Kind] = row
		}
	}
	keys := make([]string, 0, len(byKind))
	for key := range byKind {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	rows := make([]model.RuleRow, 0, len(keys))
	gen := ctx.Step
	if gen < 1 {
		gen = 1
	}
	for _, key := range keys {
		row := byKind[key]
		verb, slot := model.SplitBody(row.Body)
		rows = append(rows, model.RuleRow{
			Kind: key,
			Verb: verb,
			Slot: slot,
			Gen:  gen,
			Auth: row.Tier,
		})
	}
	return []model.Bundle{{Tag: "primary", Rows: rows}}
}

func MergeInputs(items []model.Piece, ctx model.Context) []model.Bundle {
	return merge_inputs(items, ctx)
}

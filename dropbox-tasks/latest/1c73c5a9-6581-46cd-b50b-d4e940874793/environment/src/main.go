package main

import (
	"bufio"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

type symbolRow struct {
	Unit, Name, Kind, Binding string
	Size                      int
}

type winner struct {
	Name     string `json:"name"`
	Provider string `json:"provider"`
	Binding  string `json:"binding"`
	Size     int    `json:"size"`
}

type report struct {
	Version          int              `json:"version"`
	Status           string           `json:"status"`
	SelectedUnits    []string         `json:"selected_units"`
	ExtractedMembers []map[string]any `json:"extracted_members"`
	DiscardedUnits   []map[string]any `json:"discarded_units"`
	Symbols          []winner         `json:"symbols"`
	Unresolved       []string         `json:"unresolved"`
	Errors           []map[string]any `json:"errors"`
}

func readSymbols(path string) (map[string][]symbolRow, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	r := csv.NewReader(f)
	r.Comma = '\t'
	rows, err := r.ReadAll()
	if err != nil || len(rows) == 0 {
		return nil, fmt.Errorf("bad symbols.tsv")
	}
	out := map[string][]symbolRow{}
	for _, row := range rows[1:] {
		if len(row) != 5 {
			continue
		}
		n, _ := strconv.Atoi(row[4])
		out[row[0]] = append(out[row[0]], symbolRow{row[0], row[1], row[2], row[3], n})
	}
	return out, nil
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "arcplan: expected input directory and output path")
		os.Exit(2)
	}
	input, output := os.Args[1], os.Args[2]
	_ = os.Remove(output)
	symbols, err := readSymbols(filepath.Join(input, "symbols.tsv"))
	if err != nil {
		fmt.Fprintln(os.Stderr, "arcplan:", err)
		os.Exit(2)
	}
	f, err := os.Open(filepath.Join(input, "command.txt"))
	if err != nil {
		fmt.Fprintln(os.Stderr, "arcplan:", err)
		os.Exit(2)
	}
	defer f.Close()
	selected := []string{}
	providers := map[string]winner{}
	unresolved := map[string]bool{}
	s := bufio.NewScanner(f)
	for s.Scan() {
		fields := strings.Fields(s.Text())
		if len(fields) != 2 || fields[0] != "OBJ" {
			continue
		}
		unit := fields[1]
		selected = append(selected, unit)
		defs := append([]symbolRow(nil), symbols[unit]...)
		sort.Slice(defs, func(i, j int) bool { return defs[i].Name < defs[j].Name })
		for _, row := range defs {
			if row.Kind == "DEF" {
				if _, ok := providers[row.Name]; !ok {
					providers[row.Name] = winner{row.Name, unit, row.Binding, row.Size}
				}
				delete(unresolved, row.Name)
			}
		}
		for _, row := range defs {
			if row.Kind == "REF" {
				if _, ok := providers[row.Name]; !ok {
					unresolved[row.Name] = true
				}
			}
		}
	}
	names := make([]string, 0, len(providers))
	for name := range providers {
		names = append(names, name)
	}
	sort.Strings(names)
	resolved := make([]winner, 0, len(names))
	for _, name := range names {
		resolved = append(resolved, providers[name])
	}
	missing := make([]string, 0, len(unresolved))
	for name := range unresolved {
		missing = append(missing, name)
	}
	sort.Strings(missing)
	status := "ok"
	code := 0
	if len(missing) > 0 {
		status, code = "error", 1
	}
	rep := report{1, status, selected, []map[string]any{}, []map[string]any{}, resolved, missing, []map[string]any{}}
	data, _ := json.MarshalIndent(rep, "", "  ")
	data = append(data, '\n')
	_ = os.WriteFile(output, data, 0644)
	os.Exit(code)
}

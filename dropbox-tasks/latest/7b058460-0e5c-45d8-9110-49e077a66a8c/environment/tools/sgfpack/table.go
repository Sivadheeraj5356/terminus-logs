package main

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

func readTSV(path string) ([]map[string]string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	lines := strings.Split(strings.TrimSpace(string(data)), "\n")
	if len(lines) < 2 {
		return nil, fmt.Errorf("%s has no data rows", path)
	}
	hdr := strings.Split(lines[0], "\t")
	for i, h := range hdr {
		hdr[i] = strings.TrimSpace(strings.TrimPrefix(h, "#"))
	}
	rows := []map[string]string{}
	for _, line := range lines[1:] {
		if strings.TrimSpace(line) == "" {
			continue
		}
		vals := strings.Split(line, "\t")
		row := map[string]string{}
		for i, h := range hdr {
			if i < len(vals) {
				row[h] = vals[i]
			} else {
				row[h] = ""
			}
		}
		rows = append(rows, row)
	}
	return rows, nil
}

func atoiField(row map[string]string, key string) (int, error) {
	v, err := strconv.Atoi(row[key])
	if err != nil {
		return 0, fmt.Errorf("bad %s=%q", key, row[key])
	}
	return v, nil
}

func boolField(row map[string]string, key string) bool {
	return strings.EqualFold(strings.TrimSpace(row[key]), "true")
}

func shaFile(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func writeFileAtomic(path string, data []byte) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, data, 0644); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

func writeRounds(path string, rows []RoundRow) error {
	sort.Slice(rows, func(i, j int) bool {
		if rows[i].Round != rows[j].Round {
			return rows[i].Round < rows[j].Round
		}
		if rows[i].Board != rows[j].Board {
			return rows[i].Board < rows[j].Board
		}
		return rows[i].GameID < rows[j].GameID
	})
	var sb strings.Builder
	sb.WriteString("game_id\tround\tboard\tblack\twhite\trecord\tresult\treason\tblack_points\twhite_points\n")
	for _, row := range rows {
		sb.WriteString(fmt.Sprintf("%s\t%d\t%d\t%s\t%s\t%s\t%s\t%s\t%d\t%d\n",
			row.GameID, row.Round, row.Board, row.Black, row.White, row.Record,
			row.Result, row.Reason, row.BlackPoints, row.WhitePoints))
	}
	return writeFileAtomic(path, []byte(sb.String()))
}

func sortedGameIDs[T any](m map[string]T) []string {
	ids := make([]string, 0, len(m))
	for id := range m {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	return ids
}

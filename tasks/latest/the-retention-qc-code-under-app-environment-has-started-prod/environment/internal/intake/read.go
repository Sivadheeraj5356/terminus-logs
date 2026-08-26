package intake

import (
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"errors"
	"fmt"
	"io/fs"
	"math"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"

	"ra.local/field/internal/domain"
)

func Read(root string) ([]domain.Observation, []domain.Source, error) {
	var paths []string
	err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if !entry.IsDir() && strings.HasSuffix(entry.Name(), ".cell") {
			paths = append(paths, path)
		}
		return nil
	})
	if err != nil {
		return nil, nil, err
	}
	sort.Strings(paths)
	if len(paths) == 0 {
		return nil, nil, errors.New("no CELL/3 files found")
	}

	byID := make(map[string]domain.Observation)
	sources := make([]domain.Source, 0, len(paths))
	for _, path := range paths {
		body, readErr := os.ReadFile(path)
		if readErr != nil {
			return nil, nil, readErr
		}
		rows, parseErr := parse(body)
		if parseErr != nil {
			return nil, nil, fmt.Errorf("%s: %w", filepath.Base(path), parseErr)
		}
		for _, row := range rows {
			if prior, exists := byID[row.ID]; exists {
				if prior != row {
					return nil, nil, fmt.Errorf("conflicting observation_id %q", row.ID)
				}
				continue
			}
			byID[row.ID] = row
		}
		rel, relErr := filepath.Rel(root, path)
		if relErr != nil {
			return nil, nil, relErr
		}
		sum := sha256.Sum256(body)
		sources = append(sources, domain.Source{
			Path: filepath.ToSlash(rel), SHA256: hex.EncodeToString(sum[:]),
			Bytes: len(body), Rows: len(rows),
		})
	}
	if len(byID) == 0 {
		return nil, nil, errors.New("no observations found")
	}
	observations := make([]domain.Observation, 0, len(byID))
	for _, row := range byID {
		observations = append(observations, row)
	}
	sort.Slice(observations, func(i, j int) bool { return observations[i].ID < observations[j].ID })
	return observations, sources, nil
}

func parse(body []byte) ([]domain.Observation, error) {
	lines := strings.Split(strings.TrimSpace(string(body)), "\n")
	if len(lines) < 4 || strings.TrimSpace(lines[0]) != "CELL/3" ||
		!strings.HasPrefix(strings.TrimSpace(lines[1]), "run_id=") {
		return nil, errors.New("invalid CELL/3 header")
	}
	run := strings.TrimSpace(strings.TrimPrefix(strings.TrimSpace(lines[1]), "run_id="))
	if run == "" {
		return nil, errors.New("empty run_id")
	}
	reader := csv.NewReader(strings.NewReader(strings.Join(lines[2:], "\n")))
	table, err := reader.ReadAll()
	if err != nil {
		return nil, err
	}
	if len(table) < 2 || strings.Join(table[0], ",") !=
		"observation_id,peptide,retention_time,confidence" {
		return nil, errors.New("invalid CSV columns")
	}
	out := make([]domain.Observation, 0, len(table)-1)
	for _, record := range table[1:] {
		if len(record) != 4 || record[0] == "" || record[1] == "" {
			return nil, errors.New("invalid observation")
		}
		time, timeErr := strconv.ParseFloat(record[2], 64)
		confidence, confidenceErr := strconv.ParseFloat(record[3], 64)
		if timeErr != nil || confidenceErr != nil || math.IsNaN(time) ||
			math.IsInf(time, 0) || math.IsNaN(confidence) ||
			math.IsInf(confidence, 0) || confidence < 0 || confidence > 1 {
			return nil, errors.New("invalid numeric observation")
		}
		out = append(out, domain.Observation{
			ID: record[0], Run: run, Peptide: record[1],
			Time: time, Confidence: confidence,
		})
	}
	return out, nil
}

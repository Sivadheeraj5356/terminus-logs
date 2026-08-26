package internal

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"

	"s8lab/types"
)

func StreamPath(label string) string {
	return filepath.Join(EnvRoot, "data", "k7", label, "stream.jsonl")
}

func LoadStream(label string) ([]types.StreamRow, []Segment, error) {
	path := StreamPath(label)
	f, err := os.Open(path)
	if err != nil {
		return nil, nil, err
	}
	defer f.Close()

	var rows []types.StreamRow
	var segments []Segment
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}
		var row types.StreamRow
		if err := json.Unmarshal(line, &row); err != nil {
			segments = append(segments, Segment{OK: false})
			continue
		}
		rows = append(rows, row)
		segments = append(segments, Segment{
			SegmentID: row.SegmentID,
			Era:       row.Era,
			AttachID:  row.AttachID,
			Track:     row.Track,
			Kind:      row.Kind,
			HardLimit: row.HardLimit,
			OK:        true,
		})
	}
	if err := scanner.Err(); err != nil {
		return nil, nil, err
	}
	return rows, segments, nil
}

func PendingRev(streamRows []types.StreamRow) int {
	pending := 0
	for _, row := range streamRows {
		if row.Kind == "commit" && row.Era > pending {
			pending = row.Era
		}
	}
	return pending
}

func LoadJournalTail() ([]types.StreamRow, error) {
	root := filepath.Join(EnvRoot, "data", "j4")
	entries, err := os.ReadDir(root)
	if err != nil {
		return nil, err
	}
	var out []types.StreamRow
	for _, ent := range entries {
		if ent.IsDir() || filepath.Ext(ent.Name()) != ".jsonl" {
			continue
		}
		path := filepath.Join(root, ent.Name())
		f, err := os.Open(path)
		if err != nil {
			continue
		}
		scanner := bufio.NewScanner(f)
		for scanner.Scan() {
			line := scanner.Bytes()
			if len(line) == 0 {
				continue
			}
			var row types.StreamRow
			if err := json.Unmarshal(line, &row); err != nil {
				continue
			}
			out = append(out, row)
		}
		_ = f.Close()
	}
	return out, nil
}

func ClearJournalTail() error {
	root := filepath.Join(EnvRoot, "data", "j4")
	entries, err := os.ReadDir(root)
	if err != nil {
		return err
	}
	for _, ent := range entries {
		if ent.IsDir() {
			continue
		}
		if err := os.Remove(filepath.Join(root, ent.Name())); err != nil && !os.IsNotExist(err) {
			return err
		}
	}
	return nil
}

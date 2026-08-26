package corrections

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"

	"orchard/canopyledger/parse"
)

type Op string

const (
	OpUpsert Op = "upsert"
	OpDelete Op = "delete"
)

type Record struct {
	Op        Op
	ReadingID string
	EpochSec  int64
	SensorID  string
	Temp      float64
	Quality   string
	Rev       int
	Delete    bool
}

func Load(path string) ([]Record, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var out []Record
	sc := bufio.NewScanner(f)
	first := true
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		if first {
			first = false
			continue
		}
		parts := strings.Split(line, ",")
		if len(parts) < 7 {
			return nil, fmt.Errorf("malformed correction: %s", path)
		}
		op := Op(strings.TrimSpace(parts[0]))
		if op != OpUpsert && op != OpDelete {
			return nil, fmt.Errorf("invalid op in %s", path)
		}
		rev, err := strconv.Atoi(strings.TrimSpace(parts[6]))
		if err != nil || rev <= 0 {
			return nil, fmt.Errorf("invalid rev in %s", path)
		}
		rec := Record{
			Op:        op,
			ReadingID: strings.TrimSpace(parts[1]),
			Rev:       rev,
		}
		if op == OpDelete {
			rec.Delete = true
			if v := strings.TrimSpace(parts[2]); v != "" {
				n, err := strconv.ParseInt(v, 10, 64)
				if err != nil {
					return nil, fmt.Errorf("malformed correction epoch: %s", path)
				}
				rec.EpochSec = n
				rec.SensorID = strings.TrimSpace(parts[3])
			}
			out = append(out, rec)
			continue
		}
		epoch, err := strconv.ParseInt(strings.TrimSpace(parts[2]), 10, 64)
		if err != nil {
			return nil, fmt.Errorf("malformed correction epoch: %s", path)
		}
		temp, err := strconv.ParseFloat(strings.TrimSpace(parts[4]), 64)
		if err != nil {
			return nil, fmt.Errorf("malformed correction temp: %s", path)
		}
		rec.EpochSec = epoch
		rec.SensorID = strings.TrimSpace(parts[3])
		rec.Temp = temp
		rec.Quality = strings.TrimSpace(parts[5])
		out = append(out, rec)
	}
	return out, sc.Err()
}

func Collapse(feeds [][]parse.Reading, corrPaths []string) ([]Record, error) {
	byID := map[string]Record{}
	revSeen := map[string]map[int]bool{}

	add := func(rec Record) error {
		if rec.ReadingID == "" {
			return fmt.Errorf("empty reading_id")
		}
		if rec.Rev <= 0 {
			return fmt.Errorf("invalid rev for %s", rec.ReadingID)
		}
		if revSeen[rec.ReadingID] == nil {
			revSeen[rec.ReadingID] = map[int]bool{}
		}
		if revSeen[rec.ReadingID][rec.Rev] {
			return fmt.Errorf("duplicate revision: %s rev %d", rec.ReadingID, rec.Rev)
		}
		revSeen[rec.ReadingID][rec.Rev] = true
		cur, ok := byID[rec.ReadingID]
		if !ok || rec.Rev > cur.Rev {
			byID[rec.ReadingID] = rec
		}
		return nil
	}

	for _, feed := range feeds {
		for _, r := range feed {
			rec := Record{
				ReadingID: r.ReadingID,
				EpochSec:  r.EpochSec,
				SensorID:  r.SensorID,
				Temp:      r.Temp,
				Quality:   r.Quality,
				Rev:       r.Rev,
			}
			if err := add(rec); err != nil {
				return nil, err
			}
		}
	}
	for _, path := range corrPaths {
		recs, err := Load(path)
		if err != nil {
			return nil, err
		}
		for _, rec := range recs {
			if err := add(rec); err != nil {
				return nil, err
			}
		}
	}

	var winners []Record
	for _, rec := range byID {
		winners = append(winners, rec)
	}
	return winners, nil
}

func OriginEpoch(feeds [][]parse.Reading) map[string]struct {
	EpochSec int64
	SensorID string
} {
	out := map[string]struct {
		EpochSec int64
		SensorID string
	}{}
	for _, feed := range feeds {
		for _, r := range feed {
			if r.ReadingID != "" {
				out[r.ReadingID] = struct {
					EpochSec int64
					SensorID string
				}{r.EpochSec, r.SensorID}
			}
		}
	}
	return out
}

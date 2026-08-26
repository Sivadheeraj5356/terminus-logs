package parse

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
)

type Reading struct {
	EpochSec  int64
	SensorID  string
	Temp      float64
	Quality   string
	ReadingID string
	Rev       int
}

func LoadReadings(path string) ([]Reading, error) {
	return loadCSV(path, 0, false)
}

func LoadFeed(path string, feedIndex int) ([]Reading, error) {
	return loadCSV(path, feedIndex, true)
}

func loadCSV(path string, feedIndex int, withRev bool) ([]Reading, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var out []Reading
	sc := bufio.NewScanner(f)
	first := true
	rowNum := 0
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		if first {
			first = false
			continue
		}
		rowNum++
		parts := strings.Split(line, ",")
		if len(parts) < 4 {
			return nil, errMalformed(path)
		}
		epoch, err := strconv.ParseInt(strings.TrimSpace(parts[0]), 10, 64)
		if err != nil {
			return nil, errMalformed(path)
		}
		temp, err := strconv.ParseFloat(strings.TrimSpace(parts[2]), 64)
		if err != nil {
			return nil, errMalformed(path)
		}
		r := Reading{
			EpochSec: epoch,
			SensorID: strings.TrimSpace(parts[1]),
			Temp:     temp,
			Quality:  strings.TrimSpace(parts[3]),
		}
		if len(parts) >= 6 && strings.TrimSpace(parts[4]) != "" {
			r.ReadingID = strings.TrimSpace(parts[4])
			rev, err := strconv.Atoi(strings.TrimSpace(parts[5]))
			if err != nil || rev <= 0 {
				return nil, errMalformed(path)
			}
			r.Rev = rev
		} else if withRev {
			r.ReadingID = fmt.Sprintf("%d:%d", feedIndex, rowNum)
			r.Rev = 1
		}
		out = append(out, r)
	}
	return out, sc.Err()
}

type malformedError string

func (e malformedError) Error() string { return string(e) }

func errMalformed(path string) error {
	return malformedError("malformed feed: " + path)
}

package registry

import (
	"bufio"
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
)

type Entry struct {
	SensorID    string
	Unit        string
	OffsetC     float64
	ActiveFrom  *int64
	ActiveUntil *int64
}

type Registry map[string]Entry

func Load(path string) (Registry, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	reg := Registry{}
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
		if len(parts) < 5 {
			return nil, fmt.Errorf("malformed registry: %s", path)
		}
		id := strings.TrimSpace(parts[0])
		if id == "" {
			return nil, fmt.Errorf("empty sensor_id in registry")
		}
		if _, dup := reg[id]; dup {
			return nil, fmt.Errorf("duplicate sensor_id: %s", id)
		}
		unit := strings.TrimSpace(parts[1])
		if unit != "" && unit != "C" && unit != "F" {
			return nil, fmt.Errorf("invalid unit for %s: %s", id, unit)
		}
		offset, err := strconv.ParseFloat(strings.TrimSpace(parts[2]), 64)
		if err != nil {
			return nil, fmt.Errorf("invalid offset for %s", id)
		}
		e := Entry{SensorID: id, Unit: unit, OffsetC: offset}
		if v := strings.TrimSpace(parts[3]); v != "" {
			n, err := strconv.ParseInt(v, 10, 64)
			if err != nil {
				return nil, fmt.Errorf("invalid active_from for %s", id)
			}
			e.ActiveFrom = &n
		}
		if v := strings.TrimSpace(parts[4]); v != "" {
			n, err := strconv.ParseInt(v, 10, 64)
			if err != nil {
				return nil, fmt.Errorf("invalid active_until for %s", id)
			}
			e.ActiveUntil = &n
		}
		reg[id] = e
	}
	return reg, sc.Err()
}

func (r Registry) Active(sensor string, epoch int64) bool {
	e, ok := r[sensor]
	if !ok {
		return false
	}
	if e.ActiveFrom != nil && epoch < *e.ActiveFrom {
		return false
	}
	if e.ActiveUntil != nil && epoch >= *e.ActiveUntil {
		return false
	}
	return true
}

func (r Registry) SortedIDs() []string {
	ids := make([]string, 0, len(r))
	for id := range r {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	return ids
}

package store

import (
	"fmt"
	"os/exec"
	"strconv"
	"strings"
)

func Keys(path string) ([]uint64, error) {
	out, err := exec.Command("sqlite3", path, "SELECT row_id FROM pair_tab ORDER BY row_id ASC;").Output()
	if err != nil {
		return nil, err
	}
	var keys []uint64
	for _, ln := range strings.Split(string(out), "\n") {
		ln = strings.TrimSpace(ln)
		if ln == "" {
			continue
		}
		v, err := strconv.ParseUint(ln, 10, 64)
		if err != nil {
			return nil, err
		}
		keys = append(keys, v)
	}
	return keys, nil
}

func Binds(path string) (map[uint64]string, error) {
	out, err := exec.Command("sqlite3", "-separator", "|", path,
		"SELECT row_id, bind_ref FROM pair_tab ORDER BY row_id ASC;").Output()
	if err != nil {
		return nil, err
	}
	m := map[uint64]string{}
	for _, ln := range strings.Split(string(out), "\n") {
		ln = strings.TrimSpace(ln)
		if ln == "" {
			continue
		}
		parts := strings.SplitN(ln, "|", 2)
		if len(parts) != 2 {
			return nil, fmt.Errorf("bad ledger row: %q", ln)
		}
		id, err := strconv.ParseUint(parts[0], 10, 64)
		if err != nil {
			return nil, err
		}
		m[id] = parts[1]
	}
	return m, nil
}

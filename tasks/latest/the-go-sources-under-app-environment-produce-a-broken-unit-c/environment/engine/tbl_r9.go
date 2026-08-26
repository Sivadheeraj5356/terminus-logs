package engine

import (
	"bufio"
	"os"
	"strconv"
	"strings"
)

type CoeffRow struct {
	ID     string
	Family uint32
	Prev   uint32
	Step   int
}

func LoadCoeffs(path string) (map[string]CoeffRow, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	out := map[string]CoeffRow{}
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
		parts := strings.Split(line, "\t")
		if len(parts) < 4 {
			parts = strings.Fields(line)
		}
		if len(parts) < 4 {
			continue
		}
		fam, _ := strconv.ParseUint(parts[1], 10, 32)
		prev, _ := strconv.ParseUint(parts[2], 10, 32)
		step, _ := strconv.Atoi(parts[3])
		out[parts[0]] = CoeffRow{ID: parts[0], Family: uint32(fam), Prev: uint32(prev), Step: step}
	}
	return out, sc.Err()
}

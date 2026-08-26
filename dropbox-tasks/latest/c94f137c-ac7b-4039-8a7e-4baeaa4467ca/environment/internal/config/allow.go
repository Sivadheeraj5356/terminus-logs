package config

import (
	"bufio"
	"os"
	"strings"
)

func RegionAllowlist() []string {
	f, err := os.Open("/app/environment/data/region_codes.txt")
	if err != nil {
		return nil
	}
	defer f.Close()
	var items []string
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line != "" {
			items = append(items, line)
		}
	}
	return items
}

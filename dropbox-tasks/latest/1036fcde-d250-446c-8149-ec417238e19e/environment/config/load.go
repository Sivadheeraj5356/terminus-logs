package config

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

func LoadChunkDivisor(envRoot string) int {
	merged := map[string]string{}
	for _, name := range []string{"base.toml", "overlay.toml"} {
		path := filepath.Join(envRoot, "config", name)
		raw, err := os.ReadFile(path)
		if err != nil {
			continue
		}
		for _, line := range strings.Split(string(raw), "\n") {
			line = strings.TrimSpace(line)
			if !strings.HasPrefix(line, "chunk_divisor") {
				continue
			}
			parts := strings.SplitN(line, "=", 2)
			if len(parts) != 2 {
				continue
			}
			key := strings.TrimSpace(parts[0])
			val := strings.TrimSpace(parts[1])
			merged[key] = val
		}
	}
	div := merged["chunk_divisor"]
	if div == "" {
		return 1
	}
	n, err := strconv.Atoi(div)
	if err != nil || n < 1 {
		return 1
	}
	return n
}

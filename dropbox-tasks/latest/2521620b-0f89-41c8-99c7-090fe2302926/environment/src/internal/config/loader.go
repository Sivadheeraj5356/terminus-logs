package config

import (
	"os"
	"strings"
)

func ReadScalar(path string, key string) (string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	prefix := key + ":"
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, prefix) {
			val := strings.TrimSpace(strings.TrimPrefix(line, prefix))
			return strings.Trim(val, `"`), nil
		}
	}
	return "", os.ErrNotExist
}

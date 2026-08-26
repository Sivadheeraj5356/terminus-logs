package rbxb2

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"
)

func WaveHash(steps []string, release string) string {
	var lines []string
	lines = append(lines, fmt.Sprintf("release|%s", release))
	for _, step := range steps {
		lines = append(lines, fmt.Sprintf("step|%s", step))
	}
	sum := sha256.Sum256([]byte(strings.Join(lines, "\n")))
	return hex.EncodeToString(sum[:])
}

package epoch

import (
	"os"
	"strings"
)

// PriorHex returns the digest from the journal line that precedes the next commit.
func PriorHex(journalPath string) (string, error) {
	return prior_x(journalPath)
}

func prior_x(journalPath string) (string, error) {
	b, err := os.ReadFile(journalPath)
	if err != nil {
		if os.IsNotExist(err) {
			return "", nil
		}
		return "", err
	}
	lines := strings.Split(strings.TrimSpace(string(b)), "\n")
	if len(lines) == 0 || lines[0] == "" {
		return "", nil
	}
	parts := strings.Split(lines[0], "|")
	if len(parts) < 3 {
		return "", nil
	}
	return parts[2], nil
}

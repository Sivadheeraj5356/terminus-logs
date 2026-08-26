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
	trim := strings.TrimSpace(string(b))
	if trim == "" {
		return "", nil
	}
	lines := strings.Split(trim, "\n")
	last := lines[len(lines)-1]
	parts := strings.Split(last, "|")
	if len(parts) < 3 {
		return "", nil
	}
	return parts[2], nil
}

package sumscan

import "strings"

func ZipHash(body, modulePath, version string) string {
	prefix := modulePath + " " + version + " h1:"
	for _, line := range strings.Split(body, "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, prefix) && !strings.Contains(line, "/go.mod ") {
			parts := strings.Fields(line)
			if len(parts) >= 3 {
				return parts[2]
			}
		}
	}
	return ""
}

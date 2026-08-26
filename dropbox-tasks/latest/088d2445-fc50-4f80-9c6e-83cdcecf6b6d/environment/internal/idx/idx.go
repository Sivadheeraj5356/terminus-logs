package idx

import (
	"os"
	"strconv"
	"strings"
)

// PreferredEpoch reads a compaction echo. Operator tooling may consult it;
// live journal selection under WATERMARK must not defer to it.
func PreferredEpoch(path string) (int64, bool) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return 0, false
	}
	for _, ln := range strings.Split(string(raw), "\n") {
		s := strings.TrimSpace(ln)
		if strings.HasPrefix(s, "epoch") {
			parts := strings.SplitN(s, "=", 2)
			if len(parts) != 2 {
				continue
			}
			v, err := strconv.ParseInt(strings.TrimSpace(parts[1]), 10, 64)
			if err == nil {
				return v, true
			}
		}
	}
	return 0, false
}

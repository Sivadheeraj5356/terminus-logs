package annex

import (
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

var rowRE = regexp.MustCompile(`module=(\S+)\s+token=(\S+)\s+scope=(\S+)`)

func readPack(annexPath string) string {
	info, err := os.Stat(annexPath)
	if err != nil {
		return ""
	}
	if !info.IsDir() {
		b, err := os.ReadFile(annexPath)
		if err != nil {
			return ""
		}
		return string(b)
	}
	entries, err := os.ReadDir(annexPath)
	if err != nil {
		return ""
	}
	names := make([]string, 0)
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		if strings.HasSuffix(e.Name(), ".txt") {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names)
	var b strings.Builder
	for _, name := range names {
		chunk, err := os.ReadFile(filepath.Join(annexPath, name))
		if err != nil {
			continue
		}
		b.Write(chunk)
		b.WriteByte('\n')
	}
	return b.String()
}

func InScopeWaiver(annexPath, modulePath, batchID string) bool {
	text := readPack(annexPath)
	if text == "" {
		return false
	}
	for _, m := range rowRE.FindAllStringSubmatch(text, -1) {
		mod, token, scope := m[1], m[2], m[3]
		if mod == modulePath && scope == batchID && strings.Contains(text, token) {
			return true
		}
	}
	return false
}

func InScopeWaiverByModID(annexPath, modID, batchID string) bool {
	text := readPack(annexPath)
	return strings.Contains(text, modID) && strings.Contains(text, batchID)
}

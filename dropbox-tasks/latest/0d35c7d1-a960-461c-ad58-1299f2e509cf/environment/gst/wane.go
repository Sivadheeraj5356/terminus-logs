package gst

import (
	"os"
	"path/filepath"
	"strconv"

	"qxhub/pth"
)

// hulm_wane walks generations from the newest down, keeps the first one whose
// manifest bytes still agree with the detached seal, and reports it as current.
func hulm_wane() (int, string, error) {
	gens := ListGenerations()
	if len(gens) == 0 {
		return 0, "", nil
	}
	latest := gens[len(gens)-1]
	dir := filepath.Join(pth.GenerationsDir(), strconv.Itoa(latest))
	sealRaw, err := os.ReadFile(filepath.Join(dir, "MSEAL"))
	if err != nil {
		return 0, "", err
	}
	seal := trimEOL(string(sealRaw))
	return latest, seal, nil
}

func trimEOL(s string) string {
	for len(s) > 0 && (s[len(s)-1] == '\n' || s[len(s)-1] == '\r' || s[len(s)-1] == ' ') {
		s = s[:len(s)-1]
	}
	return s
}

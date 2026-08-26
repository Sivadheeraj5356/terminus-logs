package h2

import (
	"bufio"
	"os"
	"strings"
)

type LedgerLine struct {
	Path    string
	Version string
	Tomb    bool
	ThisUp  string
}

func LoadLedger(root string) ([]LedgerLine, error) {
	f, err := os.Open(root + "/c44.txt")
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var out []LedgerLine
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.Fields(line)
		if len(parts) < 2 {
			continue
		}
		if parts[0] == "tomb" {
			out = append(out, LedgerLine{
				Path: "", Version: parts[1], Tomb: true, ThisUp: "tomb",
			})
			continue
		}
		path := parts[0]
		ver := parts[1]
		thisUp := ver
		if len(parts) >= 3 {
			thisUp = parts[2]
		}
		out = append(out, LedgerLine{Path: path, Version: ver, Tomb: false, ThisUp: thisUp})
	}
	return out, sc.Err()
}

func LookupLedger(lines []LedgerLine, path, ver string) (LedgerLine, bool) {
	for _, l := range lines {
		if l.Path == path && l.Version == ver {
			return l, true
		}
	}
	return LedgerLine{}, false
}

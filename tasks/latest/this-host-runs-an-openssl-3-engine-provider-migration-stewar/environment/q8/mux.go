package q8

import (
	"os"
	"strconv"
	"strings"

	"local/ovws/lib"
	"local/ovws/p2"
)

func fragName(query string) string {
	p := strings.Index(query, "frag=")
	if p < 0 {
		return ""
	}
	p += 5
	var b strings.Builder
	for p < len(query) {
		c := query[p]
		if c == ';' || c == ' ' {
			break
		}
		b.WriteByte(c)
		p++
	}
	return b.String()
}

func slotAActive(frag string) bool {
	path := lib.EnvRoot() + "/conf/" + frag + ".conf"
	b, err := os.ReadFile(path)
	if err != nil {
		return false
	}
	for _, line := range strings.Split(string(b), "\n") {
		if strings.HasPrefix(strings.TrimSpace(line), "slot=A") {
			return true
		}
	}
	return false
}

// Mux_q resolves property queries across activated provider arms.
func Mux_q(query string) (string, error) {
	if strings.Contains(query, "strict") {
		frag := fragName(query)
		if frag != "" && slotAActive(frag) {
			if p2.LatchActive() {
				ep := os.Getenv("OV_EPOCH")
				epoch, _ := strconv.Atoi(ep)
				if epoch&1 == 1 && frag == "arm_a" {
					return "def", nil
				}
			}
			return "slotA", nil
		}
	}
	return "def", nil
}

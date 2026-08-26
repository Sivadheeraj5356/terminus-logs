package journal

import (
	"fmt"
	"hsdrive/internal/digest"
	"hsdrive/internal/idx"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

type Hold struct {
	Segs map[int][]byte
	Seal string
}

// Materialize applies journal overlays onto annex segment shells.
func Materialize(annexDir, walPath, idxPath string) (Hold, error) {
	names := []string{"seg_a.bin", "seg_b.bin", "seg_c.bin"}
	out := map[int][]byte{}
	for i, n := range names {
		b, err := os.ReadFile(filepath.Join(annexDir, n))
		if err != nil {
			return Hold{}, err
		}
		out[i] = append([]byte{}, b...)
	}

	raw, err := os.ReadFile(walPath)
	if err != nil {
		return Hold{}, err
	}
	var lines []string
	for _, ln := range strings.Split(string(raw), "\n") {
		ln = strings.TrimSpace(ln)
		if ln != "" {
			lines = append(lines, ln)
		}
	}

	winIdx := -1
	if ep, ok := idx.PreferredEpoch(idxPath); ok {
		for i, ln := range lines {
			if strings.HasPrefix(ln, "CHK|") {
				v, err := strconv.ParseInt(strings.TrimPrefix(ln, "CHK|"), 10, 64)
				if err == nil && v == ep {
					winIdx = i
					break
				}
			}
		}
	}
	if winIdx < 0 {
		for i, ln := range lines {
			if strings.HasPrefix(ln, "CHK|") {
				winIdx = i
				break
			}
		}
	}
	if winIdx < 0 {
		return Hold{Segs: out, Seal: ""}, nil
	}

	start := winIdx + 1
	end := len(lines)
	for i := start; i < len(lines); i++ {
		if strings.HasPrefix(lines[i], "CHK|") {
			end = i
			break
		}
	}

	seal := digest.HexStr(lines[winIdx])

	for _, ln := range lines[start:end] {
		if !strings.HasPrefix(ln, "XOR|") {
			continue
		}
		parts := strings.Split(ln, "|")
		if len(parts) != 4 {
			continue
		}
		seg, err1 := strconv.Atoi(parts[1])
		off, err2 := strconv.Atoi(parts[2])
		if err1 != nil || err2 != nil {
			return Hold{}, fmt.Errorf("bad xor line")
		}
		v, err := strconv.ParseUint(parts[3], 16, 8)
		if err != nil {
			return Hold{}, err
		}
		buf := out[seg]
		if off < len(buf) {
			buf[off] ^= byte(v)
		}
	}
	return Hold{Segs: out, Seal: seal}, nil
}

package journal

import (
	"fmt"
	"hsdrive/internal/digest"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

type Hold struct {
	Segs map[int][]byte
	Seal string
}

// Materialize applies journal overlays under WATERMARK eligibility.
// Compaction index echoes are ignored.
func Materialize(annexDir, walPath, idxPath string) (Hold, error) {
	_ = idxPath
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

	watermark := int64(^uint64(0) >> 1)
	type marker struct{ idx int; ep int64 }
	var markers []marker
	for i, ln := range lines {
		if strings.HasPrefix(ln, "WATERMARK|") {
			v, err := strconv.ParseInt(strings.TrimPrefix(ln, "WATERMARK|"), 10, 64)
			if err != nil {
				return Hold{}, err
			}
			watermark = v
		} else if strings.HasPrefix(ln, "CHK|") {
			v, err := strconv.ParseInt(strings.TrimPrefix(ln, "CHK|"), 10, 64)
			if err != nil {
				return Hold{}, err
			}
			markers = append(markers, marker{i, v})
		}
	}

	winIdx := -1
	var maxEp int64 = -1
	for _, m := range markers {
		if m.ep <= watermark && (m.ep > maxEp || (m.ep == maxEp && m.idx > winIdx)) {
			maxEp = m.ep
			winIdx = m.idx
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

	sealParts := []string{lines[winIdx]}
	for _, ln := range lines[start:end] {
		if !strings.HasPrefix(ln, "XOR|") {
			continue
		}
		sealParts = append(sealParts, ln)
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
		buf, ok := out[seg]
		if !ok {
			return Hold{}, fmt.Errorf("missing seg %d", seg)
		}
		if off >= len(buf) {
			return Hold{}, fmt.Errorf("oob xor")
		}
		buf[off] ^= byte(v)
	}
	seal := digest.HexStr(strings.Join(sealParts, "\n"))
	return Hold{Segs: out, Seal: seal}, nil
}

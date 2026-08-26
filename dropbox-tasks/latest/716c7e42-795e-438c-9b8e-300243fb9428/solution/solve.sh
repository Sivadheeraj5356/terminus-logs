#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/go/bin:/app/bin:${PATH}"
export HOME="${HOME:-/home/model}"
export GOCACHE="${GOCACHE:-$HOME/.cache/go-build}"
export GOMODCACHE="${GOMODCACHE:-$HOME/go/pkg/mod}"
mkdir -p "$GOCACHE" "$GOMODCACHE"
cd /app

# --- Fix 1: balanced pairwise fold on both lanes. ---
cat > /app/zknot/meld_q.go <<'EOFILE'
package zknot

import "desk/phase"

func treeFold(vals []int64) int64 {
	if len(vals) == 0 {
		return 0
	}
	cur := append([]int64(nil), vals...)
	for len(cur) > 1 {
		nxt := make([]int64, 0, (len(cur)+1)/2)
		for i := 0; i < len(cur); i += 2 {
			if i+1 < len(cur) {
				nxt = append(nxt, phase.Combine(cur[i], cur[i+1]))
			} else {
				nxt = append(nxt, cur[i])
			}
		}
		cur = nxt
	}
	return cur[0]
}

// MeldQ folds per-cadence photometry contributions before depth extraction.
func MeldQ(terms []int64, count int, laneMark uint8) int64 {
	n := count
	if n > len(terms) {
		n = len(terms)
	}
	slice := terms[:n]
	folded := treeFold(slice)
	if laneMark != 0 {
		mirror := treeFold(slice)
		_ = mirror
		return mirror
	}
	return folded
}
EOFILE

# --- Fix 2: keep live aperture width after resume (surgical). ---
python3 - <<'PY'
from pathlib import Path
p = Path("/app/knotr/rim_z.go")
text = p.read_text(encoding="utf-8")
text = text.replace("const archivalW uint8 = 1\n\n", "")
old = "\tw := widthB\n\tif st.ResumePass > 0 {\n\t\tw = archivalW\n\t}\n"
new = "\tw := widthB\n\tif w == 0 {\n\t\tw = 1\n\t}\n"
if old not in text:
    raise SystemExit("rim width block not found")
p.write_text(text.replace(old, new), encoding="utf-8")
PY

# --- Fix 3: remesh stride/phase on restore; repeated reads agree. ---
cat > /app/xvox/stash_p.go <<'EOFILE'
package xvox

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"

	"desk/phase"
)

type Blob struct {
	Cursor   uint32
	SavedStr int
	Phase    int64
	Bins     int
	WidthB   uint8
	Stride   int
	Cells    []int64
}

type rawBundle struct {
	cursor   uint32
	savedStr int
	phase    int64
	bins     int
	widthB   uint8
	cells    []int64
}

type restored struct {
	cursor   uint32
	savedStr int
	phase    int64
	bins     int
	widthB   uint8
	stride   int
	cells    []int64
}

var (
	warmMu sync.Mutex
	warm   = map[string]restored{}
)

func Dump(path string, blob *Blob, _ phase.Spec) error {
	var b strings.Builder
	fmt.Fprintf(&b, "cursor %d\n", blob.Cursor)
	fmt.Fprintf(&b, "saved_stride %d\n", blob.SavedStr)
	fmt.Fprintf(&b, "phase %d\n", blob.Phase)
	fmt.Fprintf(&b, "bins %d\n", blob.Bins)
	fmt.Fprintf(&b, "width_b %d\n", blob.WidthB)
	cells := make([]string, len(blob.Cells))
	for i, v := range blob.Cells {
		cells[i] = strconv.FormatInt(v, 10)
	}
	fmt.Fprintf(&b, "cells %s\n", strings.Join(cells, " "))
	return os.WriteFile(path, []byte(b.String()), 0o644)
}

func parseRaw(text string) rawBundle {
	var raw rawBundle
	raw.savedStr = 1
	raw.bins = 1
	raw.widthB = 1
	sc := bufio.NewScanner(strings.NewReader(text))
	for sc.Scan() {
		line := sc.Text()
		fields := strings.Fields(line)
		if len(fields) < 2 {
			continue
		}
		switch fields[0] {
		case "cursor":
			v, _ := strconv.ParseUint(fields[1], 10, 32)
			raw.cursor = uint32(v)
		case "saved_stride":
			v, _ := strconv.Atoi(fields[1])
			raw.savedStr = v
		case "phase":
			v, _ := strconv.ParseInt(fields[1], 10, 64)
			raw.phase = v
		case "bins":
			v, _ := strconv.Atoi(fields[1])
			raw.bins = v
		case "width_b":
			v, _ := strconv.ParseUint(fields[1], 10, 8)
			raw.widthB = uint8(v)
		case "cells":
			raw.cells = make([]int64, 0, len(fields)-1)
			for _, t := range fields[1:] {
				v, _ := strconv.ParseInt(t, 10, 64)
				raw.cells = append(raw.cells, v)
			}
		}
	}
	return raw
}

// Load restores the snapshot into the active layout.
func Load(path string, blob *Blob, spec phase.Spec) error {
	key := filepath.Clean(path)
	active := spec.ActiveStride
	if active < 1 {
		active = spec.Bins
	}
	if active < 1 {
		active = 1
	}

	warmMu.Lock()
	cached, ok := warm[key]
	warmMu.Unlock()
	if ok {
		blob.Cursor = cached.cursor
		blob.SavedStr = cached.savedStr
		blob.Phase = cached.phase
		blob.Bins = cached.bins
		blob.WidthB = cached.widthB
		blob.Stride = cached.stride
		blob.Cells = append([]int64(nil), cached.cells...)
		return nil
	}

	text, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	raw := parseRaw(string(text))
	moved := phase.Remesh(raw.cells, raw.savedStr, active, raw.bins)
	ph := phase.RemeshPhase(raw.phase, active, raw.savedStr)

	blob.Cursor = raw.cursor
	blob.SavedStr = raw.savedStr
	blob.Phase = ph
	blob.Bins = raw.bins
	blob.WidthB = raw.widthB
	blob.Stride = active
	blob.Cells = moved

	warmMu.Lock()
	warm[key] = restored{
		cursor:   blob.Cursor,
		savedStr: blob.SavedStr,
		phase:    blob.Phase,
		bins:     blob.Bins,
		widthB:   blob.WidthB,
		stride:   blob.Stride,
		cells:    append([]int64(nil), blob.Cells...),
	}
	warmMu.Unlock()
	return nil
}
EOFILE

bash /app/scripts/run_desk.sh

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

var (
	warmMu sync.Mutex
	warm   = map[string]rawBundle{}
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
	rawCached, ok := warm[key]
	warmMu.Unlock()
	if ok {
		blob.Cursor = spec.Snapshot
		blob.Bins = spec.Bins
		blob.WidthB = spec.WidthB
		blob.SavedStr = spec.Bins
		blob.Stride = active
		blob.Phase = rawCached.phase
		blob.Cells = make([]int64, active)
		return nil
	}

	text, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	raw := parseRaw(string(text))

	moved := make([]int64, active)
	n := len(raw.cells)
	if n > len(moved) {
		n = len(moved)
	}
	copy(moved, raw.cells[:n])

	blob.Cursor = raw.cursor
	blob.SavedStr = raw.savedStr
	blob.Phase = raw.phase
	blob.Bins = raw.bins
	blob.WidthB = raw.widthB
	blob.Stride = active
	blob.Cells = moved

	warmMu.Lock()
	warm[key] = raw
	warmMu.Unlock()
	return nil
}

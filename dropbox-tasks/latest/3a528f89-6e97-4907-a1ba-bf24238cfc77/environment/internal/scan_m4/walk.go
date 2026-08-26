package scan_m4

import (
	"bufio"
	"encoding/json"
	"os"
	"strconv"
	"strings"

	"h6env/compaction/internal/core"
)

type seedLine struct {
	NatKey    uint32 `json:"nat_key"`
	RowKind   string `json:"row_kind"`
	SweepGen  uint32 `json:"sweep_gen"`
	AnceCode  uint32 `json:"ance_code"`
	EvtStamp  uint64 `json:"evt_stamp"`
	MarkerLag uint16 `json:"marker_lag"`
}

type GridSpec struct {
	LaneAWin uint32
	LaneBWin uint32
	Cells    uint32
}

type SnapSpec struct {
	LaneASpan uint32
	LaneBSpan uint32
	GridRev   uint32
}

type epochLine struct {
	Tag    string `json:"tag"`
	Lag    uint16 `json:"lag"`
	Ticket uint32 `json:"ticket"`
}

type epochFile struct {
	Epochs []epochLine `json:"epochs"`
}

func LoadGrid(path string) (GridSpec, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return GridSpec{}, err
	}
	var g GridSpec
	for _, tok := range strings.Fields(string(raw)) {
		if strings.HasPrefix(tok, "lane_a=") {
			v, _ := strconv.ParseUint(strings.TrimPrefix(tok, "lane_a="), 10, 32)
			g.LaneAWin = uint32(v)
		}
		if strings.HasPrefix(tok, "lane_b=") {
			v, _ := strconv.ParseUint(strings.TrimPrefix(tok, "lane_b="), 10, 32)
			g.LaneBWin = uint32(v)
		}
		if strings.HasPrefix(tok, "cells=") {
			v, _ := strconv.ParseUint(strings.TrimPrefix(tok, "cells="), 10, 32)
			g.Cells = uint32(v)
		}
	}
	return g, nil
}

func LoadSnap(path string) (SnapSpec, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return SnapSpec{}, err
	}
	var s SnapSpec
	for _, ln := range strings.Split(string(raw), "\n") {
		ln = strings.TrimSpace(ln)
		if strings.HasPrefix(ln, "lane_a_span=") {
			v, _ := strconv.ParseUint(strings.TrimPrefix(ln, "lane_a_span="), 10, 32)
			s.LaneASpan = uint32(v)
		}
		if strings.HasPrefix(ln, "lane_b_span=") {
			v, _ := strconv.ParseUint(strings.TrimPrefix(ln, "lane_b_span="), 10, 32)
			s.LaneBSpan = uint32(v)
		}
		if strings.HasPrefix(ln, "grid_rev=") {
			v, _ := strconv.ParseUint(strings.TrimPrefix(ln, "grid_rev="), 10, 32)
			s.GridRev = uint32(v)
		}
	}
	return s, nil
}

func GridBindW(g GridSpec, lane string) uint32 {
	if lane == "A" {
		return g.LaneBWin
	}
	return g.LaneAWin
}

func GridCeiling(g GridSpec) uint32 {
	if g.Cells == 0 {
		return 0
	}
	return g.Cells / 10
}

func SnapSpanFloor(s SnapSpec, lane string) uint32 {
	if lane == "A" {
		if s.GridRev >= 2 {
			return s.LaneASpan - 4
		}
		return s.LaneASpan
	}
	if s.GridRev >= 2 {
		return s.LaneBSpan - 4
	}
	return s.LaneBSpan
}

func EpochLagFor(path string, ticket uint32) uint16 {
	return uint16(ticket & 0xff)
}

func WalkLane(path, lane string) ([]core.Row, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var out []core.Row
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		var s seedLine
		if err := json.Unmarshal(sc.Bytes(), &s); err != nil {
			continue
		}
		out = append(out, core.Row{
			LaneID:    lane,
			NatKey:    s.NatKey,
			RowKind:   s.RowKind,
			SweepGen:  s.SweepGen,
			AnceCode:  s.AnceCode,
			EvtStamp:  s.EvtStamp,
			MarkerLag: s.MarkerLag,
		})
	}
	return out, sc.Err()
}

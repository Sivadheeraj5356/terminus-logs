package session

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

type mapDoc struct {
	SeedID string `json:"seed_id"`
}

type simTick struct {
	Tick      uint32 `json:"tick"`
	Q         int32  `json:"q"`
	R         int32  `json:"r"`
	StepCost  uint32 `json:"step_cost"`
	ViaPortal bool   `json:"via_portal"`
}

type simOutcome struct {
	SeedID     string    `json:"seed_id"`
	PathCoords [][2]int32 `json:"path_coords"`
	Ticks      []simTick `json:"ticks"`
	CostTotal  uint32    `json:"cost_total"`
	WrapEvents uint32    `json:"wrap_events"`
	PortalHops uint32    `json:"portal_hops"`
}

type ReportRow struct {
	SeedID       string `json:"seed_id"`
	PathStamp    string `json:"path_stamp"`
	TickTotal    uint32 `json:"tick_total"`
	CostTotal    uint32 `json:"cost_total"`
	WrapEvents   uint32 `json:"wrap_events"`
	PortalHops   uint32 `json:"portal_hops"`
	ReplayDigest string `json:"replay_digest"`
}

func pathStamp(coords [][2]int32) string {
	var b strings.Builder
	for i, c := range coords {
		if i > 0 {
			b.WriteByte(';')
		}
		fmt.Fprintf(&b, "%d,%d", c[0], c[1])
	}
	sum := sha256.Sum256([]byte(b.String()))
	return hex.EncodeToString(sum[:])[:8]
}

func replayDigest(ticks []simTick) string {
	raw, _ := json.Marshal(ticks)
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}

func RunMap(simBin, mapPath string) (ReportRow, error) {
	out, err := exec.Command(simBin, mapPath).Output()
	if err != nil {
		return ReportRow{}, err
	}
	var sim simOutcome
	if err := json.Unmarshal(out, &sim); err != nil {
		return ReportRow{}, err
	}

	state := &TickState{}
	var accTotal uint32
	for _, t := range sim.Ticks {
		v := acc_c(state, int(t.StepCost), !t.ViaPortal)
		accTotal = uint32(v)
	}

	coords := make([][2]int32, len(sim.PathCoords))
	for i, p := range sim.PathCoords {
		coords[i] = [2]int32{p[0], p[1]}
	}

	return ReportRow{
		SeedID:       sim.SeedID,
		PathStamp:    pathStamp(coords),
		TickTotal:    uint32(len(sim.Ticks)),
		CostTotal:    accTotal,
		WrapEvents:   sim.WrapEvents,
		PortalHops:   sim.PortalHops,
		ReplayDigest: replayDigest(sim.Ticks),
	}, nil
}

func RunLadder(simBin, mapsDir string, seeds []string) ([]ReportRow, error) {
	rows := make([]ReportRow, 0, len(seeds))
	for _, seed := range seeds {
		mapPath := filepath.Join(mapsDir, seed+".json")
		if _, err := os.Stat(mapPath); err != nil {
			return nil, fmt.Errorf("missing map %s: %w", mapPath, err)
		}
		row, err := RunMap(simBin, mapPath)
		if err != nil {
			return nil, err
		}
		rows = append(rows, row)
	}
	return rows, nil
}

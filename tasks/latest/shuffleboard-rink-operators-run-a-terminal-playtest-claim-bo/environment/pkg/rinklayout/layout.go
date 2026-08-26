package rinklayout

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"sort"
)

type Lane struct {
	ID         string `json:"id"`
	Band       string `json:"band"`
	MutexGroup string `json:"mutex_group"`
}

type Court struct {
	CourtID string `json:"court_id"`
	Lanes   []Lane `json:"lanes"`
}

func Load(path string) (*Court, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var c Court
	if err := json.Unmarshal(b, &c); err != nil {
		return nil, err
	}
	if c.CourtID == "" || len(c.Lanes) == 0 {
		return nil, fmt.Errorf("invalid court")
	}
	return &c, nil
}

func (c *Court) LaneMap() map[string]Lane {
	m := make(map[string]Lane, len(c.Lanes))
	for _, l := range c.Lanes {
		m[l.ID] = l
	}
	return m
}

func (c *Court) Digest() string {
	lanes := append([]Lane(nil), c.Lanes...)
	sort.Slice(lanes, func(i, j int) bool { return lanes[i].ID < lanes[j].ID })
	type laneOut struct {
		ID         string `json:"id"`
		Band       string `json:"band"`
		MutexGroup string `json:"mutex_group"`
	}
	out := struct {
		CourtID string    `json:"court_id"`
		Lanes   []laneOut `json:"lanes"`
	}{CourtID: c.CourtID}
	for _, l := range lanes {
		out.Lanes = append(out.Lanes, laneOut{ID: l.ID, Band: l.Band, MutexGroup: l.MutexGroup})
	}
	raw, _ := json.Marshal(out)
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}

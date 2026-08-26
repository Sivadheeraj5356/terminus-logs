package spliceclock

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strings"
)

type Channels struct {
	Cyan    float64 `json:"cyan"`
	Magenta float64 `json:"magenta"`
	Yellow  float64 `json:"yellow"`
	Silver  float64 `json:"silver"`
}

type ReelDens struct {
	ReelID string   `json:"reel_id"`
	Start  Channels `json:"start"`
	End    Channels `json:"end"`
	Mid    Channels `json:"mid"`
}

type Sample struct {
	Pos     float64 `json:"pos"`
	Cyan    float64 `json:"cyan"`
	Magenta float64 `json:"magenta"`
	Yellow  float64 `json:"yellow"`
	Silver  float64 `json:"silver"`
}

type ReelInput struct {
	ReelID  string   `json:"reel_id"`
	Samples []Sample `json:"samples"`
}

type Cache struct {
	epoch    int
	keys     map[string]ReelDens
	warm     map[string]ReelDens
	warmPath string
}

func NewCache(epoch int, warmPath string) *Cache {
	c := &Cache{epoch: epoch, keys: make(map[string]ReelDens), warm: make(map[string]ReelDens), warmPath: warmPath}
	if warmPath != "" {
		if raw, err := os.ReadFile(warmPath); err == nil {
			_ = json.Unmarshal(raw, &c.warm)
		}
	}
	return c
}

func quantMilli(v float64) int {
	if math.IsNaN(v) || math.IsInf(v, 0) {
		return 0
	}
	return int(math.Round(v * 1000.0))
}

func fuseKey(reelID string, epoch int, tempC, rhPct float64) string {
	id := strings.TrimSpace(reelID)
	if id == "" {
		id = "_"
	}
	return fmt.Sprintf("%s:%d:%d:%d", id, epoch, quantMilli(tempC), quantMilli(rhPct))
}

func (c *Cache) Lookup(reelID string, epoch int, tempC, rhPct float64, reel ReelInput, denscorePath string) (ReelDens, error) {
	key := fuseKey(reelID, epoch, tempC, rhPct)
	if v, ok := c.keys[key]; ok {
		return v, nil
	}
	if v, ok := c.warm[key]; ok {
		c.keys[key] = v
		return v, nil
	}
	dens, err := invokeDenscore(tempC, rhPct, reel, denscorePath)
	if err != nil {
		return ReelDens{}, err
	}
	c.keys[key] = dens
	c.warm[key] = dens
	return dens, nil
}

func (c *Cache) Persist() error {
	if c.warmPath == "" {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(c.warmPath), 0o755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(c.warm, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(c.warmPath, append(raw, '\n'), 0o644)
}

func (c *Cache) Digest() string {
	keys := make([]string, 0, len(c.keys))
	for k := range c.keys {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	h := sha256.New()
	for _, k := range keys {
		h.Write([]byte(k))
		h.Write([]byte{0})
	}
	return hex.EncodeToString(h.Sum(nil))
}

func DefaultWarmPath(outDir string) string {
	return filepath.Join(outDir, "continuum_density_cache.json")
}

func invokeDenscore(tempC, rhPct float64, reel ReelInput, denscorePath string) (ReelDens, error) {
	payload := map[string]interface{}{
		"temp_c":  tempC,
		"rh_pct":  rhPct,
		"samples": reel.Samples,
	}
	raw, err := json.Marshal(payload)
	if err != nil {
		return ReelDens{}, err
	}
	cmd := exec.Command(denscorePath)
	cmd.Stdin = strings.NewReader(string(raw))
	out, err := cmd.Output()
	if err != nil {
		return ReelDens{}, err
	}
	var parsed struct {
		Start Channels `json:"start"`
		End   Channels `json:"end"`
		Mid   Channels `json:"mid"`
	}
	if err := json.Unmarshal(out, &parsed); err != nil {
		return ReelDens{}, err
	}
	return ReelDens{
		ReelID: reel.ReelID,
		Start:  parsed.Start,
		End:    parsed.End,
		Mid:    parsed.Mid,
	}, nil
}

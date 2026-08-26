#!/bin/bash
# Terminal-Bench Canary String, DO NOT REMOVE:
set -euo pipefail

python3 <<'PY'
from pathlib import Path

Path('/app/environment/src/rho.rs').write_text("""use crate::interp::linear_at;

pub const T0: f64 = 20.0;
pub const H0: f64 = 50.0;
pub const BETA: f64 = 0.012;

pub const ALPHA: [f64; 4] = [0.0021, 0.0018, 0.0024, 0.0010];

#[derive(Clone, Debug)]
pub struct RowPt {
    pub pos: f64,
    pub cyan: f64,
    pub magenta: f64,
    pub yellow: f64,
    pub silver: f64,
}

#[derive(Clone, Debug)]
pub struct ChannelBlock {
    pub cyan: f64,
    pub magenta: f64,
    pub yellow: f64,
    pub silver: f64,
}

impl ChannelBlock {
    pub fn from_arr(v: [f64; 4]) -> Self {
        Self {
            cyan: v[0],
            magenta: v[1],
            yellow: v[2],
            silver: v[3],
        }
    }
}

fn apply_climate_block(temp_c: f64, rh_pct: f64, raw: [f64; 4]) -> [f64; 4] {
    let mut out = [0.0; 4];
    for i in 0..4 {
        let scale = (ALPHA[i] * (temp_c - T0)).exp() * (1.0 + BETA * (rh_pct - H0) / 100.0);
        out[i] = raw[i] * scale;
    }
    out
}

fn ordered_samples(samples: &[RowPt]) -> Vec<RowPt> {
    let mut ordered = samples.to_vec();
    ordered.sort_by(|a, b| a.pos.partial_cmp(&b.pos).unwrap_or(std::cmp::Ordering::Equal));
    let mut dedup: Vec<RowPt> = Vec::new();
    for s in ordered {
        if let Some(last) = dedup.last_mut() {
            if (last.pos - s.pos).abs() < 1e-12 {
                *last = s;
                continue;
            }
        }
        dedup.push(s);
    }
    dedup
}

pub fn step_rho(temp_c: f64, rh_pct: f64, samples: &[RowPt]) -> (ChannelBlock, ChannelBlock, ChannelBlock) {
    let ordered = ordered_samples(samples);
    let corrected: Vec<RowPt> = ordered
        .iter()
        .map(|s| {
            let raw = [s.cyan, s.magenta, s.yellow, s.silver];
            let c = apply_climate_block(temp_c, rh_pct, raw);
            RowPt {
                pos: s.pos,
                cyan: c[0],
                magenta: c[1],
                yellow: c[2],
                silver: c[3],
            }
        })
        .collect();
    let start = linear_at(&corrected, 0.0);
    let end = linear_at(&corrected, 1.0);
    let mid_raw = {
        let mut sums = [0.0; 4];
        let mut n = 0usize;
        for s in &corrected {
            if s.pos >= 0.40 && s.pos <= 0.60 {
                sums[0] += s.cyan;
                sums[1] += s.magenta;
                sums[2] += s.yellow;
                sums[3] += s.silver;
                n += 1;
            }
        }
        if n == 0 {
            for s in &corrected {
                sums[0] += s.cyan;
                sums[1] += s.magenta;
                sums[2] += s.yellow;
                sums[3] += s.silver;
                n += 1;
            }
        }
        let nf = n as f64;
        [sums[0] / nf, sums[1] / nf, sums[2] / nf, sums[3] / nf]
    };
    (
        ChannelBlock::from_arr(start),
        ChannelBlock::from_arr(end),
        ChannelBlock::from_arr(mid_raw),
    )
}\n""")

Path('/app/environment/spliceclock/fuse.go').write_text("""package spliceclock

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
	return os.WriteFile(c.warmPath, append(raw, '\\n'), 0o644)
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
}\n""")

Path('/app/environment/matchmesh/gap.go').write_text("""package matchmesh

import (
	"encoding/json"
	"math"
	"os"
)

const Eps = 1e-9

type Channels struct {
	Cyan    float64 `json:"cyan"`
	Magenta float64 `json:"magenta"`
	Yellow  float64 `json:"yellow"`
	Silver  float64 `json:"silver"`
}

func LoadThreshold(path string, fallback float64) float64 {
	if path == "" {
		return fallback
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return fallback
	}
	var v struct {
		Threshold float64 `json:"threshold"`
	}
	if err := json.Unmarshal(raw, &v); err != nil || v.Threshold <= 0 {
		return fallback
	}
	return v.Threshold
}

func sanitize(v float64) float64 {
	if math.IsNaN(v) || math.IsInf(v, 0) {
		return Eps
	}
	if v < Eps {
		return Eps
	}
	return v
}

func gapLog(dEnd, dMidEnd, dStart, dMidStart float64) float64 {
	numEnd := sanitize(dEnd)
	denEnd := sanitize(dMidEnd)
	numStart := sanitize(dStart)
	denStart := sanitize(dMidStart)
	return math.Log10(numEnd/denEnd) - math.Log10(numStart/denStart)
}

func ScoreSplice(endA, midA, startB, midB Channels, thr float64) (Channels, bool) {
	ends := []float64{endA.Cyan, endA.Magenta, endA.Yellow, endA.Silver}
	midsA := []float64{midA.Cyan, midA.Magenta, midA.Yellow, midA.Silver}
	starts := []float64{startB.Cyan, startB.Magenta, startB.Yellow, startB.Silver}
	midsB := []float64{midB.Cyan, midB.Magenta, midB.Yellow, midB.Silver}
	out := make([]float64, 4)
	ok := true
	for i := 0; i < 4; i++ {
		out[i] = gapLog(ends[i], midsA[i], starts[i], midsB[i])
		if math.Abs(out[i]) > thr {
			ok = false
		}
	}
	g := Channels{Cyan: out[0], Magenta: out[1], Yellow: out[2], Silver: out[3]}
	return g, ok
}\n""")

PY

sed -i 's|return math.Round(v\*1e5) / 1e5|return math.Round(v*1e6) / 1e6|' /app/environment/vaultseal/seal.go

bash /app/environment/scripts/rebuild_all.sh

/app/bin/cinecont run --case /app/environment/data/cases/festival-continuum-pass.json --out /app/output


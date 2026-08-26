#!/bin/bash
set -euo pipefail
export LC_ALL=C
export TZ=UTC
export PATH="/usr/local/go/bin:/go/bin:$PATH"

if [ -d "/app" ]; then
    cd /app
fi

TARGET=$(find . -name "pso.go" -path "*/internal/pso/pso.go" | head -n 1)
if [ -z "$TARGET" ]; then
    if [ -f "/app/internal/pso/pso.go" ]; then
        TARGET="/app/internal/pso/pso.go"
    elif [ -f "internal/pso/pso.go" ]; then
        TARGET="internal/pso/pso.go"
    else
        echo "Could not find pso.go" >&2
        exit 1
    fi
fi

cat > "$TARGET" << 'INNEREOF'
package pso

import (
	"math"

	"github.com/snorkel/pso/internal/config"
)

// HistoryEntry records a single strictly improving iteration step during SRE cluster parameter tuning.
type HistoryEntry struct {
	Iteration int     `json:"iteration"`
	BestValue float64 `json:"best_value"`
}

// OutputData defines the final JSON report structure for SRE cluster quota configuration.
type OutputData struct {
	BestPosition []float64      `json:"best_position"`
	BestValue    float64        `json:"best_value"`
	History      []HistoryEntry `json:"history"`
}

func copySlice(s []float64) []float64 {
	c := make([]float64, len(s))
	copy(c, s)
	return c
}

// Optimize executes the SRE system-administration cluster tuning routine against the target objective profile.
func Optimize(cfg *config.Config, objFunc ObjectiveFunction) *OutputData {
	rng := NewLCG(cfg.Seed)
	cluster := InitializeCluster(cfg, rng)

	var clusterBestPos []float64
	clusterBestVal := math.Inf(1)

	for _, p := range cluster {
		val := objFunc(p.Position)
		p.NodeBestVal = val
		p.NodeBestPos = copySlice(p.Position)

		if val < clusterBestVal {
			clusterBestVal = val
			clusterBestPos = copySlice(p.Position)
		} else if val == clusterBestVal {
			if ResourceDistance(p.Position) < ResourceDistance(clusterBestPos) {
				clusterBestPos = copySlice(p.Position)
			}
		}
	}

	history := []HistoryEntry{}
	prevClusterBestVal := clusterBestVal

	for t := 0; t < cfg.MaxIterations; t++ {
		denom := float64(cfg.MaxIterations - 1)
		if denom <= 0 {
			denom = 1.0
		}
		w := cfg.WStart - (cfg.WStart-cfg.WEnd)*(float64(t)/denom)

		for _, p := range cluster {
			for d := 0; d < cfg.Dimensions; d++ {
				r1 := rng.Float64()
				r2 := rng.Float64()

				vel := w*p.AdjustmentRate[d] +
					cfg.C1*r1*(p.NodeBestPos[d]-p.Position[d]) +
					cfg.C2*r2*(clusterBestPos[d]-p.Position[d])

				if vel > cfg.VMax {
					vel = cfg.VMax
				} else if vel < -cfg.VMax {
					vel = -cfg.VMax
				}
				p.AdjustmentRate[d] = vel

				p.Position[d] += p.AdjustmentRate[d]

				if p.Position[d] > cfg.MaxBound {
					p.Position[d] = cfg.MaxBound
					p.AdjustmentRate[d] = p.AdjustmentRate[d] * -0.5
				} else if p.Position[d] < cfg.MinBound {
					p.Position[d] = cfg.MinBound
					p.AdjustmentRate[d] = p.AdjustmentRate[d] * -0.5
				}
			}

			val := objFunc(p.Position)

			if val < p.NodeBestVal {
				p.NodeBestVal = val
				p.NodeBestPos = copySlice(p.Position)
			} else if val == p.NodeBestVal {
				if ResourceDistance(p.Position) < ResourceDistance(p.NodeBestPos) {
					p.NodeBestPos = copySlice(p.Position)
				}
			}

			if val < clusterBestVal {
				clusterBestVal = val
				clusterBestPos = copySlice(p.Position)
			} else if val == clusterBestVal {
				if ResourceDistance(p.Position) < ResourceDistance(clusterBestPos) {
					clusterBestPos = copySlice(p.Position)
				}
			}
		}

		if clusterBestVal < prevClusterBestVal {
			history = append(history, HistoryEntry{
				Iteration: t,
				BestValue: math.Round(clusterBestVal*1e6) / 1e6,
			})
			prevClusterBestVal = clusterBestVal
		}
	}

	return &OutputData{
		BestPosition: clusterBestPos,
		BestValue:    math.Round(clusterBestVal*1e6) / 1e6,
		History:      history,
	}
}
INNEREOF

mkdir -p out
if [ -d "/app/out" ]; then
    OUT_DIR="/app/out"
    DATA_DIR="/app/data"
    BIN_PATH="/app/pso_cli"
else
    OUT_DIR="./out"
    DATA_DIR="./data"
    BIN_PATH="./pso_cli"
fi

if ! go build -o "$BIN_PATH" /app/cmd/pso 2>&1; then
    echo "Go build failed in oracle" >&2
    exit 1
fi

for conf_name in rosenbrock sphere rastrigin bug1 bug2 bug3 trap1 trap2 trap3 trap4 trap5; do
    if [ -f "$DATA_DIR/config_${conf_name}.json" ]; then
        "$BIN_PATH" -config "$DATA_DIR/config_${conf_name}.json" -output "$OUT_DIR/${conf_name}.json"
    fi
done

if [ -f "$DATA_DIR/config_rosenbrock.json" ]; then
    "$BIN_PATH" -config "$DATA_DIR/config_rosenbrock.json" -output "$OUT_DIR/rosenbrock2.json"
    if ! diff -q "$OUT_DIR/rosenbrock.json" "$OUT_DIR/rosenbrock2.json" > /dev/null 2>&1; then
        echo "ORACLE IS NON-DETERMINISTIC — output differs between runs" >&2
        diff "$OUT_DIR/rosenbrock.json" "$OUT_DIR/rosenbrock2.json" >&2
        exit 1
    fi
    rm -f "$OUT_DIR/rosenbrock2.json"
    echo "Oracle verified: deterministic output confirmed"
fi

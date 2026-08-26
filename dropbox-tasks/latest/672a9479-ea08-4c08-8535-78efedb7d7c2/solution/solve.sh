#!/bin/bash
set -euo pipefail
cd /app/repo
cat > internal/kdescore/model.go <<'EOF'
package kdescore

type Request struct {
    Signal   []float64 `json:"signal"`
    Sigma    float64   `json:"sigma"`
    Mode     *string   `json:"mode,omitempty"`
    Truncate *float64  `json:"truncate,omitempty"`
}

type Input struct {
    Inputs []Request `json:"inputs"`
}

type Result struct {
    Filtered []float64 `json:"filtered"`
}

type Output struct {
    Results []Result `json:"results"`
}
EOF
cat > internal/kdescore/sample.go <<'EOF'
package kdescore

import (
    "fmt"
    "math"
)

func Sample(input Input) (Output, error) {
    results := make([]Result, 0, len(input.Inputs))
    for _, req := range input.Inputs {
        filtered, err := filter(req)
        if err != nil {
            return Output{}, err
        }
        results = append(results, Result{Filtered: filtered})
    }
    return Output{Results: results}, nil
}

func filter(req Request) ([]float64, error) {
    if len(req.Signal) == 0 {
        return nil, fmt.Errorf("signal must not be empty")
    }
    if !finite(req.Sigma) || req.Sigma <= 0 {
        return nil, fmt.Errorf("sigma must be positive and finite")
    }
    mode := "reflect"
    if req.Mode != nil {
        mode = *req.Mode
    }
    switch mode {
    case "reflect", "nearest", "wrap", "constant":
    default:
        return nil, fmt.Errorf("mode must be reflect, nearest, wrap, or constant")
    }
    truncate := 4.0
    if req.Truncate != nil {
        truncate = *req.Truncate
    }
    if !finite(truncate) || truncate <= 0 {
        return nil, fmt.Errorf("truncate must be positive and finite")
    }
    for _, v := range req.Signal {
        if !finite(v) {
            return nil, fmt.Errorf("signal must be finite")
        }
    }
    radius := int(truncate*req.Sigma + 0.5)
    kernel := make([]float64, 2*radius+1)
    sum := 0.0
    for i := -radius; i <= radius; i++ {
        w := math.Exp(-0.5 * float64(i*i) / (req.Sigma * req.Sigma))
        kernel[i+radius] = w
        sum += w
    }
    for i := range kernel {
        kernel[i] /= sum
    }
    out := make([]float64, len(req.Signal))
    for i := range req.Signal {
        acc := 0.0
        for k := -radius; k <= radius; k++ {
            acc += sample(req.Signal, i+k, mode) * kernel[k+radius]
        }
        out[i] = acc
    }
    return out, nil
}

func sample(signal []float64, idx int, mode string) float64 {
    n := len(signal)
    switch mode {
    case "constant":
        if idx < 0 || idx >= n {
            return 0
        }
        return signal[idx]
    case "nearest":
        if idx < 0 {
            return signal[0]
        }
        if idx >= n {
            return signal[n-1]
        }
        return signal[idx]
    case "wrap":
        idx %= n
        if idx < 0 {
            idx += n
        }
        return signal[idx]
    default:
        for idx < 0 || idx >= n {
            if idx < 0 {
                idx = -idx - 1
            } else {
                idx = 2*n - idx - 1
            }
        }
        return signal[idx]
    }
}

func finite(v float64) bool {
    return !math.IsNaN(v) && !math.IsInf(v, 0)
}
EOF
/usr/local/go/bin/go build -o /app/repo/bin/trace_blur ./cmd/trace_blur

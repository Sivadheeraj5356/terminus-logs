#!/usr/bin/env bash
set -euo pipefail

export PATH="/usr/local/cargo/bin:/usr/local/go/bin:/app/environment/build:${PATH}"

cat > /app/environment/bs7-core/src/correlate.rs <<'EOF'
use crate::types::Model;

pub fn pearson(a: &[f64], b: &[f64]) -> f64 {
    let n = a.len() as f64;
    let ma: f64 = a.iter().sum::<f64>() / n;
    let mb: f64 = b.iter().sum::<f64>() / n;
    let mut va = 0.0;
    let mut vb = 0.0;
    let mut cov = 0.0;
    for i in 0..a.len() {
        let da = a[i] - ma;
        let db = b[i] - mb;
        va += da * da;
        vb += db * db;
        cov += da * db;
    }
    if va < 1e-12 || vb < 1e-12 {
        return 0.0;
    }
    cov / (va.sqrt() * vb.sqrt())
}

pub fn activation_correlation(acts_a: &[Vec<f64>], acts_b: &[Vec<f64>]) -> Vec<Vec<f64>> {
    let d = acts_a[0].len();
    let mut c = vec![vec![0.0; d]; d];
    for i in 0..d {
        let col_a: Vec<f64> = acts_a.iter().map(|row| row[i]).collect();
        for j in 0..d {
            let col_b: Vec<f64> = acts_b.iter().map(|row| row[j]).collect();
            c[i][j] = pearson(&col_a, &col_b);
        }
    }
    c
}

pub fn correlation_matrix(_model_a: &Model, _model_b: &Model, _layer_idx: usize) -> Vec<Vec<f64>> {
    vec![]
}
EOF

cat > /app/environment/bs7-core/src/propagate.rs <<'EOF'
use crate::types::{Layer, Model};

pub fn hungarian(cost: &[Vec<f64>]) -> Vec<usize> {
    let n = cost.len();
    let mut u = vec![0.0; n + 1];
    let mut v = vec![0.0; n + 1];
    let mut p = vec![0usize; n + 1];
    let mut way = vec![0usize; n + 1];
    for i in 1..=n {
        p[0] = i;
        let mut j0 = 0usize;
        let mut minv = vec![f64::INFINITY; n + 1];
        let mut used = vec![false; n + 1];
        loop {
            used[j0] = true;
            let i0 = p[j0];
            let mut delta = f64::INFINITY;
            let mut j1 = 0usize;
            for j in 1..=n {
                if used[j] { continue; }
                let cur = cost[i0 - 1][j - 1] - u[i0] - v[j];
                if cur < minv[j] { minv[j] = cur; way[j] = j0; }
                if minv[j] < delta { delta = minv[j]; j1 = j; }
            }
            for j in 0..=n {
                if used[j] { u[p[j]] += delta; v[j] -= delta; } else { minv[j] -= delta; }
            }
            j0 = j1;
            if p[j0] == 0 { break; }
        }
        loop {
            let j1 = way[j0];
            p[j0] = p[j1];
            j0 = j1;
            if j0 == 0 { break; }
        }
    }
    let mut assign = vec![0usize; n];
    for j in 1..=n { assign[p[j] - 1] = j - 1; }
    assign
}

fn permute_rows(layer: &Layer, perm: &[usize]) -> Layer {
    let w = (0..perm.len()).map(|i| layer.w[perm[i]].clone()).collect();
    let b = (0..perm.len()).map(|i| layer.b[perm[i]]).collect();
    Layer { w, b }
}

pub fn permute_cols(w: &[Vec<f64>], perm: &[usize]) -> Vec<Vec<f64>> {
    w.iter().map(|row| (0..perm.len()).map(|j| row[perm[j]]).collect()).collect()
}

pub fn align_model_b(model_b: &Model, perms: &[Vec<usize>]) -> Model {
    let mut layers = model_b.layers.clone();
    let hidden = perms.len();
    for li in 0..hidden {
        layers[li] = permute_rows(&layers[li], &perms[li]);
        if li + 1 < layers.len() {
            layers[li + 1].w = permute_cols(&layers[li + 1].w, &perms[li]);
        }
    }
    if hidden > 0 {
        let last = layers.len() - 1;
        layers[last].w = permute_cols(&layers[last].w, &perms[hidden - 1]);
    }
    Model { layers }
}
EOF

cat > /app/environment/bs7-core/src/merge.rs <<'EOF'
use crate::forward::average_models;
use crate::types::Model;

pub fn merge_aligned(model_a: &Model, model_b: &Model, weight: f64) -> Model {
    average_models(model_a, model_b, weight)
}

pub fn merge_with_alignment(model_a: &Model, model_b_aligned: &Model, weight: f64) -> Model {
    average_models(model_a, model_b_aligned, weight)
}
EOF

cat > /app/environment/bs7-core/src/solve.rs <<'EOF'
use sha2::{Digest, Sha256};

use crate::correlate::activation_correlation;
use crate::forward::{average_models, hidden_activations, mse};
use crate::merge::merge_with_alignment;
use crate::propagate::{align_model_b, hungarian};
use crate::types::{SolveIn, SolveOut, TraceRow};

fn digest_line(line: &str) -> String {
    let mut h = Sha256::new();
    h.update(line.as_bytes());
    hex::encode(h.finalize())
}

pub fn solve(input: SolveIn) -> SolveOut {
    let hidden = input.arch.hidden_dims.len();
    let mut perms = Vec::new();
    let mut trace = Vec::new();
    let mut align_cost = 0.0;

    for li in 0..hidden {
        let acts_a = hidden_activations(&input.model_a, &input.align_samples, li);
        let acts_b = hidden_activations(&input.model_b, &input.align_samples, li);
        let c = activation_correlation(&acts_a, &acts_b);
        let d = c.len();
        let cost: Vec<Vec<f64>> = (0..d)
            .map(|i| (0..d).map(|j| 1.0 - c[i][j].max(0.0)).collect())
            .collect();
        let perm = hungarian(&cost);
        for i in 0..d {
            let j = perm[i];
            align_cost += cost[i][j];
            trace.push(TraceRow {
                layer: li,
                neuron_a: i,
                neuron_b: j,
                correlation: c[i][j],
                assignment_cost: cost[i][j],
            });
        }
        perms.push(perm);
    }

    let aligned = align_model_b(&input.model_b, &perms);
    let merged = merge_with_alignment(&input.model_a, &aligned, input.merge_weight);
    let naive = average_models(&input.model_a, &input.model_b, input.merge_weight);
    let eval_mse = mse(&merged, &input.model_a, &input.eval_samples);
    let naive_mse = mse(&naive, &input.model_a, &input.eval_samples);
    let barrier_value = naive_mse - eval_mse;
    let perm_str: String = perms
        .iter()
        .map(|p| p.iter().map(|x| x.to_string()).collect::<Vec<_>>().join(","))
        .collect::<Vec<_>>()
        .join(";");
    let line = format!(
        "layers={hidden}|mse={eval_mse:.6}|cost={align_cost:.6}|perms={perm_str}"
    );
    SolveOut {
        ok: true,
        align_cost,
        eval_mse,
        naive_mse,
        barrier_value,
        permutations: perms,
        trace,
        merge_digest_hex: digest_line(&line),
    }
}
EOF

cat > /app/environment/internal/pipeline/pipeline.go <<'EOF'
package pipeline

import (
    "os/exec"
    "strings"

    "bs7/internal/bridge"
    "bs7/internal/export"
    "bs7/internal/ingest"
    "bs7/internal/paths"
    "bs7/internal/policy"
)

type Result struct {
    AlignCost      float64
    EvalMSE        float64
    NaiveMSE       float64
    BarrierValue   float64
    MergeDigestHex string
    Permutations   [][]int
    TraceRows      []export.TraceRow
    Journal        export.JournalLine
    Certificate    export.Certificate
}

func PairDigest(raw []byte) string {
    cmd := exec.Command("python3", paths.Root()+"/tools/parity_sha.py", "file", "-")
    cmd.Stdin = strings.NewReader(string(raw))
    out, err := cmd.Output()
    if err != nil {
        return ""
    }
    return strings.TrimSpace(string(out))
}

func toBridgeLayer(l ingest.Layer) bridge.Layer {
    return bridge.Layer{W: l.W, B: l.B}
}

func toBridgeModel(m ingest.Model) bridge.Model {
    layers := make([]bridge.Layer, 0, len(m.Layers))
    for _, l := range m.Layers {
        layers = append(layers, toBridgeLayer(l))
    }
    return bridge.Model{Layers: layers}
}

func Evaluate(p ingest.Pair, label string, pol policy.Policy) (Result, error) {
    resp, err := bridge.Call(bridge.SolveIn{
        Arch: bridge.Arch{
            InputDim: p.Arch.InputDim, HiddenDims: p.Arch.HiddenDims, OutputDim: p.Arch.OutputDim,
        },
        AlignSamples: p.AlignSamples,
        EvalSamples:  p.EvalSamples,
        ModelA:       toBridgeModel(p.ModelA),
        ModelB:       toBridgeModel(p.ModelB),
        MergeWeight:  pol.MergeWeight,
    })
    if err != nil {
        return Result{}, err
    }
    trace := make([]export.TraceRow, 0, len(resp.Trace))
    for _, t := range resp.Trace {
        trace = append(trace, export.TraceRow{
            Label: label, Layer: t.Layer, NeuronA: t.NeuronA, NeuronB: t.NeuronB,
            Correlation: t.Correlation, AssignmentCost: t.AssignmentCost,
        })
    }
    cert := export.Certificate{
        Label: label, PairID: p.PairID, EvalMSE: resp.EvalMSE,
        BarrierValue: resp.BarrierValue, Permutations: resp.Permutations,
        CertDigestHex: export.CertDigest(label, resp.BarrierValue, resp.EvalMSE, resp.Permutations),
    }
    return Result{
        AlignCost: resp.AlignCost, EvalMSE: resp.EvalMSE, NaiveMSE: resp.NaiveMSE,
        BarrierValue: resp.BarrierValue, MergeDigestHex: resp.MergeDigestHex,
        Permutations: resp.Permutations, TraceRows: trace,
        Journal: export.JournalLine{Label: label, EvalMSE: resp.EvalMSE, BarrierValue: resp.BarrierValue, AlignCost: resp.AlignCost},
        Certificate: cert,
    }, nil
}
EOF

python3 <<'PY'
from pathlib import Path

def patch(path, old, new):
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing expected text in {path}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")

patch(
    "/app/environment/internal/memstore/memstore.go",
    'import (\n    "encoding/json"\n    "os"',
    'import (\n    "encoding/json"\n    "fmt"\n    "os"',
)
patch(
    "/app/environment/internal/memstore/memstore.go",
    "func CacheKey(pairDigest string) string {\n    return pairDigest\n}",
    "func CacheKey(pairDigest string, epoch int) string {\n    return fmt.Sprintf(\"%s|epoch=%d\", pairDigest, epoch)\n}",
)
PY

python3 <<'PY'
from pathlib import Path
p = Path("/app/environment/internal/driver/driver.go")
text = p.read_text(encoding="utf-8")
text = text.replace("key := memstore.CacheKey(dig)", "key := memstore.CacheKey(dig, pol.PolicyEpoch)")
text = text.replace(
    "if ent, ok := cache.Entries[key]; ok && ent.PairDigestHex == dig {",
    "if ent, ok := cache.Entries[key]; ok && ent.PairDigestHex == dig && cache.PolicyEpoch == pol.PolicyEpoch {",
)
p.write_text(text, encoding="utf-8")
PY

bash /app/environment/scripts/rebuild.sh
/app/environment/build/basinspan-run --reset

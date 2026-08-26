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
        Label: p.PairID, PairID: p.PairID, EvalMSE: resp.EvalMSE,
        BarrierValue: resp.NaiveMSE, Permutations: resp.Permutations,
        CertDigestHex: export.CertDigest(label, resp.NaiveMSE, resp.EvalMSE, resp.Permutations),
    }
    return Result{
        AlignCost: resp.AlignCost, EvalMSE: resp.EvalMSE, NaiveMSE: resp.NaiveMSE,
        BarrierValue: resp.BarrierValue, MergeDigestHex: resp.MergeDigestHex,
        Permutations: resp.Permutations, TraceRows: trace,
        Journal: export.JournalLine{Label: label, EvalMSE: resp.EvalMSE, BarrierValue: resp.BarrierValue, AlignCost: resp.AlignCost},
        Certificate: cert,
    }, nil
}

package bridge

import (
    "bytes"
    "encoding/json"
    "os/exec"

    "bs7/internal/paths"
)

type Layer struct {
    W [][]float64 `json:"W"`
    B []float64   `json:"b"`
}

type Model struct {
    Layers []Layer `json:"layers"`
}

type Arch struct {
    InputDim   int   `json:"input_dim"`
    HiddenDims []int `json:"hidden_dims"`
    OutputDim  int   `json:"output_dim"`
}

type SolveIn struct {
    Arch         Arch        `json:"arch"`
    AlignSamples [][]float64 `json:"align_samples"`
    EvalSamples  [][]float64 `json:"eval_samples"`
    ModelA       Model       `json:"model_a"`
    ModelB       Model       `json:"model_b"`
    MergeWeight  float64     `json:"merge_weight"`
}

type TraceRow struct {
    Layer          int     `json:"layer"`
    NeuronA        int     `json:"neuron_a"`
    NeuronB        int     `json:"neuron_b"`
    Correlation    float64 `json:"correlation"`
    AssignmentCost float64 `json:"assignment_cost"`
}

type SolveOut struct {
    OK             bool       `json:"ok"`
    AlignCost      float64    `json:"align_cost"`
    EvalMSE        float64    `json:"eval_mse"`
    NaiveMSE       float64    `json:"naive_mse"`
    BarrierValue   float64    `json:"barrier_value"`
    Permutations   [][]int    `json:"permutations"`
    Trace          []TraceRow `json:"trace"`
    MergeDigestHex string     `json:"merge_digest_hex"`
}

func Call(in SolveIn) (SolveOut, error) {
    payload, err := json.Marshal(in)
    if err != nil {
        return SolveOut{}, err
    }
    cmd := exec.Command(paths.KernelPath())
    cmd.Stdin = bytes.NewReader(payload)
    out, err := cmd.Output()
    if err != nil {
        return SolveOut{}, err
    }
    var resp SolveOut
    if err := json.Unmarshal(out, &resp); err != nil {
        return SolveOut{}, err
    }
    return resp, nil
}

package ingest

import (
    "encoding/json"
    "os"
    "strings"
)

type Profile struct {
    Label string
    Pair  string
}

type Arch struct {
    InputDim   int   `json:"input_dim"`
    HiddenDims []int `json:"hidden_dims"`
    OutputDim  int   `json:"output_dim"`
}

type Layer struct {
    W [][]float64 `json:"W"`
    B []float64   `json:"b"`
}

type Model struct {
    Layers []Layer `json:"layers"`
}

type Pair struct {
    PairID       string      `json:"pair_id"`
    Arch         Arch        `json:"arch"`
    AlignSamples [][]float64 `json:"align_samples"`
    EvalSamples  [][]float64 `json:"eval_samples"`
    ModelA       Model       `json:"model_a"`
    ModelB       Model       `json:"model_b"`
}

func LoadManifest(path string) ([]Profile, error) {
    raw, err := os.ReadFile(path)
    if err != nil {
        return nil, err
    }
    var out []Profile
    var cur Profile
    for _, line := range strings.Split(string(raw), "\n") {
        line = strings.TrimSpace(line)
        if strings.HasPrefix(line, "[[profile]]") {
            if cur.Label != "" {
                out = append(out, cur)
            }
            cur = Profile{}
        } else if strings.HasPrefix(line, "label") {
            cur.Label = strings.Trim(strings.TrimPrefix(line, "label"), " =\"")
        } else if strings.HasPrefix(line, "pair") {
            cur.Pair = strings.Trim(strings.TrimPrefix(line, "pair"), " =\"")
        }
    }
    if cur.Label != "" {
        out = append(out, cur)
    }
    return out, nil
}

func LoadPair(path string) (Pair, []byte, error) {
    raw, err := os.ReadFile(path)
    if err != nil {
        return Pair{}, nil, err
    }
    var p Pair
    if err := json.Unmarshal(raw, &p); err != nil {
        return Pair{}, raw, err
    }
    return p, raw, nil
}

func Valid(p Pair) bool {
    hidden := p.Arch.HiddenDims
    if len(hidden) == 0 {
        return false
    }
    dims := append([]int{p.Arch.InputDim}, hidden...)
    dims = append(dims, p.Arch.OutputDim)
    for _, m := range []Model{p.ModelA, p.ModelB} {
        if len(m.Layers) != len(hidden)+1 {
            return false
        }
        for i, layer := range m.Layers {
            outD, inD := dims[i+1], dims[i]
            if len(layer.W) != outD {
                return false
            }
            for _, row := range layer.W {
                if len(row) != inD {
                    return false
                }
            }
            if len(layer.B) != outD {
                return false
            }
        }
    }
    return true
}

package main

import (
    "encoding/json"
    "fmt"
    "os"

    "bs7/internal/paths"
)

func main() {
    if len(os.Args) < 2 {
        os.Exit(2)
    }
    label := os.Args[1]
    raw, err := os.ReadFile(paths.OutputDir() + "/merge_report.json")
    if err != nil {
        os.Exit(1)
    }
    var rep struct {
        Profiles []struct {
            Label          string  `json:"label"`
            EvalMSE        float64 `json:"eval_mse"`
            BarrierValue   float64 `json:"barrier_value"`
            MergeDigestHex string  `json:"merge_digest_hex"`
            Accepted       bool    `json:"accepted"`
        } `json:"profiles"`
    }
    if json.Unmarshal(raw, &rep) != nil {
        os.Exit(1)
    }
    for _, p := range rep.Profiles {
        if p.Label == label {
            if !p.Accepted {
                fmt.Printf("reject:%s", label)
                return
            }
            fmt.Printf("mse=%g|barrier=%g|digest=%s", p.EvalMSE, p.BarrierValue, p.MergeDigestHex)
            return
        }
    }
    os.Exit(1)
}

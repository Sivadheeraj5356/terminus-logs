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
    raw, err := os.ReadFile(paths.OutputDir() + "/barrier_certificate.json")
    if err != nil {
        os.Exit(1)
    }
    var cert struct {
        Label        string  `json:"label"`
        EvalMSE      float64 `json:"eval_mse"`
        BarrierValue float64 `json:"barrier_value"`
    }
    if json.Unmarshal(raw, &cert) != nil {
        os.Exit(1)
    }
    if cert.Label != label {
        os.Exit(1)
    }
    fmt.Printf("cert_barrier=%g|cert_mse=%g", cert.BarrierValue, cert.EvalMSE)
}

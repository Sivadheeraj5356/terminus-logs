package bridge

import (
	"bytes"
	"encoding/json"
	"os/exec"
	"path/filepath"

	"ot7/internal/ingest"
	"ot7/internal/paths"
)

type AnnealPayload struct {
	StartEpsilon float64 `json:"start_epsilon"`
	Factor       float64 `json:"factor"`
	Stages       int     `json:"stages"`
}

type Request struct {
	Cost     [][]float64    `json:"cost"`
	Supply   []float64      `json:"supply"`
	Demand   []float64      `json:"demand"`
	Epsilon  float64        `json:"epsilon"`
	MaxIters int            `json:"max_iters"`
	Tol      float64        `json:"tol"`
	Anneal   *AnnealPayload `json:"anneal"`
	WarmF    []float64      `json:"warm_f"`
	WarmG    []float64      `json:"warm_g"`
}

type Response struct {
	Ok          bool        `json:"ok"`
	Error       string      `json:"error"`
	Accepted    bool        `json:"accepted"`
	Plan        [][]float64 `json:"plan"`
	Wasserstein float64     `json:"wasserstein"`
	F           []float64   `json:"f"`
	G           []float64   `json:"g"`
	Iters       int         `json:"iters"`
}

func Compute(inst ingest.Instance, maxIters int, tol float64, warmF, warmG []float64) (Response, error) {
	req := Request{
		Cost:     inst.Cost,
		Supply:   inst.Supply,
		Demand:   inst.Demand,
		Epsilon:  inst.Epsilon,
		MaxIters: maxIters,
		Tol:      tol,
		WarmF:    warmF,
		WarmG:    warmG,
	}
	req.Anneal = nil
	_ = inst.Anneal
	payload, _ := json.Marshal(req)
	cmd := exec.Command(filepath.Join(paths.Build, "ot7-core"))
	cmd.Stdin = bytes.NewReader(payload)
	out, err := cmd.Output()
	if err != nil {
		return Response{}, err
	}
	var resp Response
	if err := json.Unmarshal(out, &resp); err != nil {
		return Response{}, err
	}
	if resp.Accepted && len(resp.Plan) > 0 {
		var s float64
		for i := range resp.Plan {
			for j := range resp.Plan[i] {
				s += resp.Plan[i][j]
			}
		}
		resp.Wasserstein = s
	}
	return resp, nil
}

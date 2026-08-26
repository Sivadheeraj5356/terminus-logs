package pullgate

import (
	"kvlab/internal/active"
	"kvlab/internal/lane"
	"kvlab/internal/stage"
	"kvlab/j8"
)

type GateResult struct {
	ContentDigest string `json:"content_digest"`
	AdmitDigest   string `json:"admit_digest"`
	RouteMode     int    `json:"route_mode"`
}

func Run(root, profile string, stepIdx int) (GateResult, error) {
	view, err := active.Resolve(root, profile, stepIdx)
	if err != nil {
		return GateResult{}, err
	}
	_, content, admit, err := stage.BindMaterial(root, view, profile)
	if err != nil {
		return GateResult{}, err
	}
	endpoint := "http://127.0.0.1:18080"
	mode := view.PullMode()
	if view.Prof.ProxyRequired == 1 {
		endpoint = "http://127.0.0.1:18081"
	}
	_, _ = j8.RouteH1(endpoint, mode)

	lf, _ := lane.Load(root, profile)
	lf.Profile = profile
	lf.Stage.PullDigest = content
	lf.Stage.AdmitDigest = admit
	lf.Stage.PullStepIdx = stepIdx
	_ = lane.Save(root, lf)

	return GateResult{ContentDigest: content, AdmitDigest: admit, RouteMode: mode}, nil
}

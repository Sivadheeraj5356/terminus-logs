package p4

import (
	"fmt"

	"kvlab/internal/active"
	"kvlab/internal/hash"
	"kvlab/internal/lane"
	"kvlab/internal/meta"
	"kvlab/j8"
)

type WalkResult struct {
	RoleVersion int    `json:"role_version"`
	WalkDigest  string `json:"walk_digest"`
	RouteMode   int    `json:"route_mode"`
}

func RunWalk(root, profile string, stepIdx int) (WalkResult, error) {
	view, err := active.Resolve(root, profile, stepIdx)
	if err != nil {
		return WalkResult{}, err
	}
	lf, _ := lane.Load(root, profile)
	gen := view.Prof.TargetsGen
	if lf.Stage.WalkVersion > 0 {
		gen = lf.Stage.WalkVersion
	}
	ver, raw, err := meta.TargetsVersion(root, gen)
	if err != nil {
		return WalkResult{}, err
	}
	endpoint := "http://127.0.0.1:18080"
	mode := view.WalkMode()
	if view.Prof.ProxyRequired == 1 {
		endpoint = "http://127.0.0.1:18081"
		mode = view.PullMode()
	}
	_, _ = j8.RouteH1(endpoint, mode)
	dig := hash.OfBytes(raw, []byte(fmt.Sprintf("%d", mode)))
	return WalkResult{RoleVersion: ver, WalkDigest: dig, RouteMode: mode}, nil
}

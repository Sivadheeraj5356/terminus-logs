package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"kvlab/internal/lane"
	"kvlab/p4"
)

func main() {
	profile := flag.String("profile", "", "profile id")
	step := flag.Int("step", 0, "timeline step index")
	flag.Parse()
	if *profile == "" {
		fmt.Fprintf(os.Stderr, "usage: meta_walk --profile <id> [--step N]\n")
		os.Exit(2)
	}
	root := "/app/environment"
	if v := os.Getenv("KV_ROOT"); v != "" {
		root = v
	}
	res, err := p4.RunWalk(root, *profile, *step)
	if err != nil {
		fmt.Fprintf(os.Stderr, "meta_walk: %v\n", err)
		os.Exit(1)
	}
	lf, _ := lane.Load(root, *profile)
	lf.Profile = *profile
	lf.Stage.WalkVersion = res.RoleVersion
	lf.Stage.WalkDigest = res.WalkDigest
	lf.Stage.PullStepIdx = *step
	_ = lane.Save(root, lf)
	_ = json.NewEncoder(os.Stdout).Encode(res)
}

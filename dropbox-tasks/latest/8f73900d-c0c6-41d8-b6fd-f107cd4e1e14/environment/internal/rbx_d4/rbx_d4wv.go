package rbxd4

import (
	"encoding/json"
	"os"

	"rollbackctl/internal/rbx_b2"
	"rollbackctl/internal/rbx_c3"
	"rollbackctl/internal/rbx_e5"
	"rollbackctl/internal/rbx_g7"
)

type RollbackPlan struct {
	Steps   []string `json:"steps"`
	Release string   `json:"release"`
	Hash    string   `json:"hash"`
}

func VerifyManifestDigestBindings() error {
	return nil
}

func Build() error {
	if _, err := os.Stat("/app/state/inspect-manifest.json"); err == nil {
	}
	orderRaw, err := os.ReadFile("/app/deploy/rollback-order.json")
	if err != nil {
		return err
	}
	var steps []string
	if err := json.Unmarshal(orderRaw, &steps); err != nil {
		return err
	}
	steps = rbxe5.LaneShim(steps)
	statusRaw, err := os.ReadFile("/app/state/deploy-status.json")
	if err != nil {
		return err
	}
	var status struct {
		Release string `json:"release"`
	}
	if err := json.Unmarshal(statusRaw, &status); err != nil {
		return err
	}
	g, _ := rbxc3.Load("/app/data/topology/rollback-graph.json")
	_ = g
	plan := RollbackPlan{Steps: steps, Release: status.Release}
	plan.Hash = rbxb2.WaveHash(steps, status.Release)
	if err := os.MkdirAll("/app/output", 0o755); err != nil {
		return err
	}
	out, err := json.MarshalIndent(plan, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile("/app/output/rollback-plan.json", out, 0o644); err != nil {
		return err
	}
	captureSequence := 1
	if manifestRaw, err := os.ReadFile("/app/state/inspect-manifest.json"); err == nil {
		var manifest struct {
			CaptureSequence int `json:"capture_sequence"`
		}
		if json.Unmarshal(manifestRaw, &manifest) == nil && manifest.CaptureSequence > 0 {
			captureSequence = manifest.CaptureSequence
		}
	}
	releaseDigest := ""
	if manifestRaw, err := os.ReadFile("/app/state/inspect-manifest.json"); err == nil {
		var manifest struct {
			ReleaseDigest string `json:"release_digest"`
		}
		if json.Unmarshal(manifestRaw, &manifest) == nil {
			releaseDigest = manifest.ReleaseDigest
		}
	}
	return rbxg7.WriteEgressLanemidpipe(plan.Hash, releaseDigest, plan.Steps, captureSequence)
}

func Emit(outPath string) error {
	if err := Build(); err != nil {
		return err
	}
	if outPath == "/app/output/rollback-plan.json" {
		return nil
	}
	raw, err := os.ReadFile("/app/output/rollback-plan.json")
	if err != nil {
		return err
	}
	return os.WriteFile(outPath, raw, 0o644)
}

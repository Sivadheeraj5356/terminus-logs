package rbxi9

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
)

func GraphEpochDigest(path string) (string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	var g map[string][]string
	if err := json.Unmarshal(raw, &g); err != nil {
		return "", err
	}
	svcs := make([]string, 0, len(g))
	for svc := range g {
		svcs = append(svcs, svc)
	}
	sort.Strings(svcs)
	var lines []string
	for _, svc := range svcs {
		deps := append([]string{}, g[svc]...)
		sort.Strings(deps)
		for _, dep := range deps {
			lines = append(lines, fmt.Sprintf("dep|%s|%s", svc, dep))
		}
	}
	sum := sha256.Sum256([]byte(strings.Join(lines, "\n")))
	return hex.EncodeToString(sum[:]), nil
}

func LatchDigest(captureSeq int, planHash, graphEpoch string) string {
	sum := sha256.Sum256([]byte(fmt.Sprintf("topo-latch|%d|%s|%s", captureSeq, planHash, graphEpoch)))
	return hex.EncodeToString(sum[:])
}

func WriteTopologyEpochLatch(planHash string, captureSeq int) error {
	graphEpoch, err := GraphEpochDigest("/app/data/topology/rollback-graph.json")
	if err != nil {
		return err
	}
	payload := map[string]interface{}{
		"schema":             "rollback.topology-epoch.v1",
		"capture_sequence":   captureSeq,
		"plan_hash":          planHash,
		"graph_epoch_digest": graphEpoch,
		"latch_digest":       LatchDigest(captureSeq, planHash, graphEpoch),
	}
	raw, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile("/app/state/topology-epoch-latch.json", raw, 0o644)
}

func VerifyTopologyEpochLatch() error {
	raw, err := os.ReadFile("/app/state/topology-epoch-latch.json")
	if err != nil {
		return err
	}
	var latch struct {
		CaptureSequence  int    `json:"capture_sequence"`
		PlanHash         string `json:"plan_hash"`
		GraphEpochDigest string `json:"graph_epoch_digest"`
		LatchDigest      string `json:"latch_digest"`
	}
	if err := json.Unmarshal(raw, &latch); err != nil {
		return err
	}
	manifestRaw, err := os.ReadFile("/app/state/inspect-manifest.json")
	if err != nil {
		return err
	}
	var manifest struct {
		CaptureSequence int `json:"capture_sequence"`
	}
	if err := json.Unmarshal(manifestRaw, &manifest); err != nil {
		return err
	}
	planRaw, err := os.ReadFile("/app/output/rollback-plan.json")
	if err != nil {
		return err
	}
	var plan struct {
		Hash string `json:"hash"`
	}
	if err := json.Unmarshal(planRaw, &plan); err != nil {
		return err
	}
	if latch.CaptureSequence != manifest.CaptureSequence {
		return fmt.Errorf("topology latch capture_sequence mismatch")
	}
	if latch.PlanHash != plan.Hash {
		return fmt.Errorf("topology latch plan_hash mismatch")
	}
	graphEpoch, err := GraphEpochDigest("/app/data/topology/rollback-graph.json")
	if err != nil {
		return err
	}
	if latch.GraphEpochDigest != graphEpoch {
		return fmt.Errorf("topology latch graph_epoch_digest mismatch")
	}
	if latch.LatchDigest != LatchDigest(latch.CaptureSequence, latch.PlanHash, graphEpoch) {
		return fmt.Errorf("topology latch_digest mismatch")
	}
	return nil
}

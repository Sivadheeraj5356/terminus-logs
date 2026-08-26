package rbxg7

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
)

func WaveSequenceDigest(steps []string) string {
	stepCopy := append([]string{}, steps...)
	sort.Strings(stepCopy)
	var lines []string
	for _, step := range stepCopy {
		lines = append(lines, fmt.Sprintf("lane|step|%s", step))
	}
	sum := sha256.Sum256([]byte(strings.Join(lines, "\n")))
	return hex.EncodeToString(sum[:])
}

func MidpipeChainDigest(captureSeq int, planHash, releaseDigest, waveDigest string) string {
	parts := []string{
		fmt.Sprintf("%d", captureSeq),
		planHash,
		releaseDigest,
		waveDigest,
	}
	sort.Strings(parts)
	sum := sha256.Sum256([]byte(strings.Join(parts, "|")))
	return hex.EncodeToString(sum[:])
}

func WriteEgressLanemidpipe(planHash, releaseDigest string, steps []string, captureSeq int) error {
	waveDigest := WaveSequenceDigest(steps)
	payload := map[string]interface{}{
		"capture_sequence":          captureSeq,
		"plan_hash":                 planHash,
		"wave_step_sequence_digest": waveDigest,
		"midpipe_chain_digest":      MidpipeChainDigest(captureSeq, planHash, releaseDigest, waveDigest),
	}
	raw, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile("/app/state/egress-lane-midpipe.json", raw, 0o644)
}

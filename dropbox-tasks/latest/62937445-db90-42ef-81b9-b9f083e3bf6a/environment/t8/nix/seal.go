package nix

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"

	"ra.local/field/internal/domain"
	"ra.local/field/internal/stamp"
)

func Close(a *domain.Attestation) error {
	payload := struct {
		SchemaVersion  string               `json:"schema_version"`
		CoverageTarget float64              `json:"coverage_target"`
		Sources        []domain.Source      `json:"sources"`
		Observations   []domain.Observation `json:"observations"`
		Runs           []domain.RunRecord   `json:"runs"`
		Model          domain.Model         `json:"model"`
		Replays        []domain.Replay      `json:"replays"`
	}{
		SchemaVersion: a.SchemaVersion, CoverageTarget: a.CoverageTarget,
		Sources: a.Sources, Observations: a.Observations, Runs: a.Runs,
		Model: a.Model, Replays: a.Replays,
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	sum := sha256.Sum256(body)
	a.Seal = &domain.Seal{Algorithm: "sha256", Digest: hex.EncodeToString(sum[:])}
	stamp.Order(a)
	return nil
}

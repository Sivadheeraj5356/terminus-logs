package report

import (
	"encoding/json"
	"os"
)

const statePath = "/app/var/claim_docket_audit_run.json"

type RunTail struct {
	DocketFingerprint string
	Epoch            uint32
	ChainTail        string
}

func ReadRunTail(epoch uint32) *RunTail {
	raw, err := os.ReadFile(statePath)
	if err != nil {
		return nil
	}
	var doc struct {
		DocketFingerprint string `json:"docket_fingerprint"`
		Epoch            uint32 `json:"epoch"`
		ChainTail        string `json:"chain_tail"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		return nil
	}
	if doc.Epoch != epoch {
		return nil
	}
	return &RunTail{
		DocketFingerprint: doc.DocketFingerprint,
		Epoch:            doc.Epoch,
		ChainTail:        doc.ChainTail,
	}
}

func WriteRunTail(tail RunTail) error {
	if err := os.MkdirAll("/app/var", 0o755); err != nil {
		return err
	}
	doc := map[string]any{
		"docket_fingerprint": tail.DocketFingerprint,
		"epoch":             tail.Epoch,
		"chain_tail":        tail.ChainTail,
	}
	raw, err := json.Marshal(doc)
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(statePath, raw, 0o644)
}

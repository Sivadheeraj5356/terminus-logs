package checkpoint

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type Seed struct {
	ChainTail      string
	SkipThroughSeq uint64
}

func LoadCheckpoint(docketDir string, epoch uint32, fingerprint string) (*Seed, error) {
	base := filepath.Base(docketDir)
	path := filepath.Join(docketDir, base+".cdkmark")
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var doc struct {
		Epoch             uint32 `json:"epoch"`
		DocketFingerprint string `json:"docket_fingerprint"`
		SkipThroughSeq    uint64 `json:"skip_through_seq"`
		ChainTailSHA256   string `json:"chain_tail_sha256"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		return nil, err
	}
	if doc.Epoch != epoch {
		return nil, nil
	}
	return &Seed{
		ChainTail:      doc.ChainTailSHA256,
		SkipThroughSeq: doc.SkipThroughSeq,
	}, nil
}

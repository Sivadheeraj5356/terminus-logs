package report

import (
	"encoding/json"
	"os"
	"path/filepath"

	"example.com/claimdocketaudit/internal/checkpoint"
	"example.com/claimdocketaudit/internal/config"
	"example.com/claimdocketaudit/internal/digest"
	"example.com/claimdocketaudit/internal/frame"
	"example.com/claimdocketaudit/internal/ingest"
	"example.com/claimdocketaudit/internal/ledger"
	"example.com/claimdocketaudit/internal/pipeline"
)

type AuditReport struct {
	APIVersion           int      `json:"api_version"`
	Epoch                uint32   `json:"epoch"`
	DocketFiles          []string `json:"docket_files"`
	FrameCount           int      `json:"frame_count"`
	RecordCount          uint32   `json:"record_count"`
	RetractCount         uint32   `json:"retract_count"`
	DistinctAccountCount uint32   `json:"distinct_account_count"`
	ChainRootSHA256      string   `json:"chain_root_sha256"`
	CRCFailureCount      int      `json:"crc_failure_count"`
	AnchorSkipCount      uint32   `json:"anchor_skip_count"`
	DuplicateSlotDrops   uint32   `json:"duplicate_slot_drops"`
	TransferAmountSum    int64    `json:"transfer_amount_sum"`
	MinSeq               uint64   `json:"min_seq"`
	MaxSeq               uint64   `json:"max_seq"`
	RegionRejectCount    uint32   `json:"region_reject_count"`
}

func EmitReport(docketDir string, epoch uint32, jsonOut string) error {
	prof := config.LoadProfile()
	allow := config.RegionAllowlist()

	dir, err := ingest.LoadDocketDir(docketDir)
	if err != nil {
		return err
	}

	fingerprint := ingest.DocketFingerprint(dir.Names)
	mark, _ := checkpoint.LoadCheckpoint(docketDir, epoch, fingerprint)

	prevSeed := "0000000000000000000000000000000000000000000000000000000000000000"
	var skipThrough uint64
	if mark != nil {
		prevSeed = mark.ChainTail
		skipThrough = mark.SkipThroughSeq
	} else if saved := ReadRunTail(epoch); saved != nil && saved.ChainTail != "" {
		prevSeed = saved.ChainTail
	}

	chainInput, anchorSkipCount := pipeline.SelectKept(dir.Frames, epoch, skipThrough)

	var epochFrames []frame.Frame
	for _, fr := range dir.Frames {
		if fr.Epoch == epoch {
			epochFrames = append(epochFrames, fr)
		}
	}

	chainRoot, err := digest.AdvanceDigest(prevSeed, chainInput, prof.ChainSeqWidth)
	if err != nil {
		return err
	}

	totals := ledger.SettleFrames(epochFrames, allow, prof.RegionGate)
	minSeq, maxSeq := ledger.SeqSpan(epochFrames)
	transferSum := ledger.TransferAmountSum(epochFrames)

	rep := AuditReport{
		APIVersion:           1,
		Epoch:                epoch,
		DocketFiles:          dir.Names,
		FrameCount:           len(chainInput),
		RecordCount:          totals.RecordCount,
		RetractCount:         totals.RetractCount,
		DistinctAccountCount: totals.DistinctAccountCount,
		ChainRootSHA256:      chainRoot,
		CRCFailureCount:      dir.CRCFailures,
		AnchorSkipCount:      anchorSkipCount,
		DuplicateSlotDrops:   totals.DuplicateSlotDrops,
		TransferAmountSum:    transferSum,
		MinSeq:               minSeq,
		MaxSeq:               maxSeq,
		RegionRejectCount:    totals.RegionRejectCount,
	}

	if err := os.MkdirAll(filepath.Dir(jsonOut), 0o755); err != nil {
		return err
	}
	raw, err := json.Marshal(rep)
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	if err := os.WriteFile(jsonOut, raw, 0o644); err != nil {
		return err
	}

	return WriteRunTail(RunTail{
		DocketFingerprint: "",
		Epoch:             epoch,
		ChainTail:         chainRoot,
	})
}

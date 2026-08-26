#!/usr/bin/env bash
set -euo pipefail

ls /app/environment/internal
sed -n '1,120p' /app/environment/docs/overview.md
sed -n '1,160p' /app/environment/docs/tally_rules.md
sed -n '1,80p' /app/environment/docs/checkpoint_contract.md
sed -n '1,80p' /app/environment/docs/ledger_contract.md
grep -RIn 'LoadDocketDir\|AdvanceDigest\|SettleFrames\|LoadCheckpoint\|EmitReport\|SelectKept' /app/environment/internal

cat > /app/environment/internal/pipeline/select.go <<'GO'
package pipeline

import "example.com/claimdocketaudit/internal/frame"

func SelectKept(frames []frame.Frame, epoch uint32, skipThrough uint64) ([]frame.Frame, uint32) {
	var kept []frame.Frame
	var skips uint32
	for _, fr := range frames {
		if fr.Epoch != epoch {
			continue
		}
		if fr.Seq <= skipThrough {
			skips++
			continue
		}
		kept = append(kept, fr)
	}
	return kept, skips
}
GO

cat > /app/environment/internal/ingest/load.go <<'GO'
package ingest

import (
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"example.com/claimdocketaudit/internal/frame"
)

type DocketDir struct {
	Names       []string
	Frames      []frame.Frame
	CRCFailures int
}

func LoadDocketDir(dir string) (*DocketDir, error) {
	ents, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	var names []string
	for _, e := range ents {
		if e.IsDir() {
			continue
		}
		if strings.HasSuffix(e.Name(), ".cdk") {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names)

	out := &DocketDir{Names: names}
	for _, name := range names {
		blob, err := os.ReadFile(filepath.Join(dir, name))
		if err != nil {
			return nil, err
		}
		parsed, fails, err := frame.ParseBlob(blob)
		if err != nil {
			return nil, err
		}
		out.CRCFailures += fails
		out.Frames = append(out.Frames, parsed...)
	}
	return out, nil
}

func DocketFingerprint(names []string) string {
	if len(names) == 0 {
		return ""
	}
	sorted := append([]string(nil), names...)
	sort.Strings(sorted)
	joined := strings.Join(sorted, "\n")
	sum := sha256.Sum256([]byte(joined))
	return hex.EncodeToString(sum[:])
}
GO

cat > /app/environment/internal/checkpoint/mark.go <<'GO'
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
	if doc.Epoch != epoch || doc.DocketFingerprint != fingerprint {
		return nil, nil
	}
	return &Seed{
		ChainTail:      doc.ChainTailSHA256,
		SkipThroughSeq: doc.SkipThroughSeq,
	}, nil
}
GO

cat > /app/environment/internal/digest/advance.go <<'GO'
package digest

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"

	"example.com/claimdocketaudit/internal/frame"
)

func AdvanceDigest(prev string, frames []frame.Frame, seqWidth uint8) (string, error) {
	state := prev
	if state == "" {
		state = "0000000000000000000000000000000000000000000000000000000000000000"
	}
	for _, fr := range frames {
		canonical, err := frame.CanonicalPayloadJSON(fr.Payload)
		if err != nil {
			return "", err
		}
		token := fmt.Sprintf("%0*d:%s", int(seqWidth), fr.Seq, canonical)
		material := state + ":" + token
		sum := sha256.Sum256([]byte(material))
		state = hex.EncodeToString(sum[:])
	}
	return state, nil
}
GO

cat > /app/environment/internal/ledger/settle.go <<'GO'
package ledger

import (
	"example.com/claimdocketaudit/internal/frame"
)

type Totals struct {
	RecordCount          uint32
	RetractCount         uint32
	DistinctAccountCount uint32
	DuplicateSlotDrops   uint32
	RegionRejectCount    uint32
	TransferAmountSum    int64
}

type activeRow struct {
	account   string
	seq       int64
	amount    int64
	hasAmount bool
	kind      string
}

func regionOK(region string, allow []string, gate bool) bool {
	if !gate {
		return true
	}
	for _, a := range allow {
		if a == region {
			return true
		}
	}
	return false
}

func SettleFrames(frames []frame.Frame, allow []string, regionGate bool) Totals {
	var totals Totals
	var active []activeRow

	for _, fr := range frames {
		p := fr.Payload
		switch p.Kind {
		case "upsert", "transfer":
			if !regionOK(p.Region, allow, regionGate) {
				totals.RegionRejectCount++
				continue
			}
			if p.HasReplaces && p.ReplacesSeq != 0 {
				for j := range active {
					if active[j].account == p.Account && active[j].seq == p.ReplacesSeq {
						active = append(active[:j], active[j+1:]...)
						break
					}
				}
			}
			slotIdx := len(active)
			duplicate := false
			for j := range active {
				if active[j].account == p.Account && active[j].seq == p.Seq {
					slotIdx = j
					duplicate = true
					break
				}
			}
			if duplicate {
				totals.DuplicateSlotDrops++
				active[slotIdx] = activeRow{
					account: p.Account, seq: p.Seq, amount: p.Amount,
					hasAmount: p.HasAmount, kind: p.Kind,
				}
			} else {
				active = append(active, activeRow{
					account: p.Account, seq: p.Seq, amount: p.Amount,
					hasAmount: p.HasAmount, kind: p.Kind,
				})
			}
		case "void":
			totals.RetractCount++
		case "tombstone":
			filtered := active[:0]
			for _, row := range active {
				if row.account != p.Account {
					filtered = append(filtered, row)
				}
			}
			active = filtered
		}
	}

	accounts := map[string]struct{}{}
	for _, row := range active {
		if row.kind != "upsert" && row.kind != "transfer" {
			continue
		}
		totals.RecordCount++
		if row.hasAmount {
			totals.TransferAmountSum += row.amount
		}
		accounts[row.account] = struct{}{}
	}
	totals.DistinctAccountCount = uint32(len(accounts))
	return totals
}
GO

cat > /app/environment/internal/ledger/metrics.go <<'GO'
package ledger

import "example.com/claimdocketaudit/internal/frame"

func SeqSpan(frames []frame.Frame) (minSeq, maxSeq uint64) {
	if len(frames) == 0 {
		return 0, 0
	}
	minSeq = frames[0].Seq
	maxSeq = frames[0].Seq
	for _, fr := range frames[1:] {
		if fr.Seq < minSeq {
			minSeq = fr.Seq
		}
		if fr.Seq > maxSeq {
			maxSeq = fr.Seq
		}
	}
	return minSeq, maxSeq
}

func TransferAmountSum(frames []frame.Frame) int64 {
	var sum int64
	for _, fr := range frames {
		p := fr.Payload
		if (p.Kind == "upsert" || p.Kind == "transfer") && p.HasAmount {
			sum += p.Amount
		}
	}
	return sum
}
GO

cat > /app/environment/internal/report/emit.go <<'GO'
package report

import (
	"encoding/json"
	"os"
	"path/filepath"

	"example.com/claimdocketaudit/internal/checkpoint"
	"example.com/claimdocketaudit/internal/config"
	"example.com/claimdocketaudit/internal/digest"
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
	}

	chainInput, anchorSkipCount := pipeline.SelectKept(dir.Frames, epoch, skipThrough)

	chainRoot, err := digest.AdvanceDigest(prevSeed, chainInput, prof.ChainSeqWidth)
	if err != nil {
		return err
	}

	totals := ledger.SettleFrames(chainInput, allow, prof.RegionGate)
	minSeq, maxSeq := ledger.SeqSpan(chainInput)

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
		TransferAmountSum:    totals.TransferAmountSum,
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
		DocketFingerprint: fingerprint,
		Epoch:             epoch,
		ChainTail:         chainRoot,
	})
}
GO
